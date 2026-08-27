"""Structural object lowering: layout, copies, literals, member access, methods, and object results.

Split from ``lower.py``; methods run as part of ``_Lowerer``.
"""

from __future__ import annotations

from dataclasses import replace

from ...reporting import Span
from ...semantic import builtins, hir, ty
from ...semantic.hir_display import type_to_dewy


class _ObjectLowering:
    def _object_expression_owns_fresh_storage(self, node: hir.AST) -> bool:
        node = self._copy_source_expression(node)
        return isinstance(node, (hir.ObjectLiteral, hir.FunctionCall))

    def _lower_object_argument(
        self,
        call: hir.FunctionCall,
        arg: hir.AST,
    ) -> tuple[list[hir.AST], hir.AST]:
        """Lower one object-typed value argument of ``call``.

        The bare handle is passed, because the callee prologue either clones
        it or, for a proven read-only parameter, borrows it. When a place
        argument in the same call exposes the same binding's storage, a
        borrowing callee could observe mid-call writes, so the caller clones
        the argument first.
        """
        if isinstance(arg.type, ty.ObjectType):
            place_roots = self._call_place_argument_roots(call)
            if place_roots:
                base: hir.AST = arg
                while True:
                    if (
                        isinstance(base, hir.Block)
                        and not base.scoped
                        and len(base.items) == 1
                    ):
                        base = base.items[0]
                    elif isinstance(base, hir.MemberAccess):
                        base = base.value
                    elif isinstance(base, hir.Index):
                        base = base.array
                    else:
                        break
                if (
                    isinstance(base, hir.ExpressedIdentifier)
                    and base.binding_id in place_roots
                ):
                    return self._clone_object_value(arg, arg.type)
        return self._extract_object_pointer(arg)

    def _clone_object_value(
        self,
        node: hir.AST,
        object_type: ty.ObjectType,
        *,
        arena: bool = False,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Materialize an independent structural object value (in the arena when it must outlive the frame)."""

        source_prelude, source = self._extract_object_pointer(node)
        size, _offsets = self._object_layout(object_type, node)
        target = self._new_object_temp(node.loc)
        statements: list[hir.AST] = [
            *source_prelude,
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64',
                self._object_allocation(node.loc, size, arena=arena),
            ),
            *self._object_copy(target, source, object_type, node.loc, arena=arena),
        ]
        return statements, target

    def _independent_object_value(
        self,
        node: hir.AST,
        object_type: ty.ObjectType,
    ) -> tuple[list[hir.AST], hir.AST]:
        """Produce an independently mutable object value from one expression."""

        if self._object_expression_owns_fresh_storage(node):
            return self._extract_object_pointer(node)
        return self._clone_object_value(node, object_type)

    def _allocate_object_result_value(
        self,
        object_type: ty.ObjectType,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Allocate an object and its exact mutable result fields in the caller."""

        size, _offsets = self._object_layout(
            object_type,
            hir.Void(loc, ty.VOID_TYPE),
        )
        target = self._new_object_temp(loc)
        statements: list[hir.AST] = [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64',
                self._object_allocation(loc, size),
            )
        ]
        statements.extend(
            self._initialize_object_result_storage(target, object_type, loc)
        )
        return statements, target

    def _initialize_object_result_storage(
        self,
        dest: hir.AST,
        object_type: ty.ObjectType,
        loc: Span,
    ) -> list[hir.AST]:
        """Prepare array fields recursively within existing object storage."""

        _size, offsets = self._object_layout(
            object_type,
            hir.Void(loc, ty.VOID_TYPE),
        )
        statements: list[hir.AST] = []
        for field in object_type.fields:
            address = self._field_address(dest, offsets[field.name], loc)
            if isinstance(field.type, ty.ArrayType) and field.type.length is None:
                continue  # a handle slot the callee fills with an arena-backed array
            if isinstance(field.type, ty.ArrayType):
                nested_statements, nested = self._allocate_array_result_value(
                    field.type,
                    loc,
                )
                statements.extend(nested_statements)
                statements.extend(
                    self._value_store(nested, address, field.type, loc)
                )
            elif isinstance(field.type, ty.ObjectType):
                statements.extend(
                    self._initialize_object_result_storage(
                        address,
                        field.type,
                        loc,
                    )
                )
        return statements

    def _new_object_temp(self, loc: Span) -> hir.ExpressedIdentifier:
        while True:
            name = f'__dewy_object_{self.next_object_temp}'
            self.next_object_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(loc, 'int64', name)

    def _new_object_name(self, role: str) -> str:
        while True:
            name = f'__dewy_object_{role}_{self.next_object_temp}'
            self.next_object_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

    @classmethod
    def _object_result_fields_are_returnable(
        cls,
        object_type: ty.ObjectType,
    ) -> bool:
        """Whether field copying needs no callee-owned mutable storage."""

        for field in object_type.fields:
            if (
                isinstance(field.type, ty.ArrayType)
                and not cls._array_result_elements_are_returnable(field.type)
            ):
                return False
            if (
                isinstance(field.type, ty.ObjectType)
                and not cls._object_result_fields_are_returnable(field.type)
            ):
                return False
        return True

    def _object_layout(
        self,
        object_type: ty.ObjectType,
        node: hir.AST,
    ) -> tuple[int, dict[str, int]]:
        offset = 0
        align = 1
        offsets: dict[str, int] = {}
        for field in object_type.fields:
            size, field_align = self._field_size_align(field.type, node)
            offset = (offset + field_align - 1) // field_align * field_align
            offsets[field.name] = offset
            offset += size
            align = max(align, field_align)
        size = (offset + align - 1) // align * align if align else offset
        return max(size, 1), offsets

    def _field_size_align(self, type_: ty.Type, node: hir.AST) -> tuple[int, int]:
        if type_ == 'bool':
            return 1, 1
        layout = ty.fixed_integer_layout(type_)
        if layout is not None:
            width, _signed = layout
            size = width // 8
            return size, size
        if self._is_handle_type(type_) or ty.is_user_nominal(type_):
            return 8, 8
        if self._field_union_members(type_) is not None:
            return 16, 8  # an inline union cell: tag word and payload word, no trees
        if isinstance(type_, ty.ObjectType):
            size, offsets = self._object_layout(type_, node)
            align = 1
            for field in type_.fields:
                _field_size, field_align = self._field_size_align(field.type, node)
                align = max(align, field_align)
            return size, align
        self._target_error(node, f'object field layout `{type_to_dewy(type_)}`')

    @staticmethod
    def _field_union_members(type_: ty.Type) -> tuple[ty.TypeExpr, ...] | None:
        """The storage members of a union-typed field (an optional is the
        two-member union `undefined | T`, whose tags coincide with optional cells)."""
        members = ty.runtime_union_members(type_)
        if members is not None:
            return members
        payload = ty.optional_payload(type_)
        if payload is not None:
            return ('undefined', payload)
        return None

    @staticmethod
    def _is_handle_type(type_: ty.Type) -> bool:
        return isinstance(
            type_,
            (
                ty.ArrayType,
                ty.FunctionType,
                ty.StringLiteralType,
                ty.BinaryLiteralType,
                ty.StringType,
            ),
        ) or (
            isinstance(type_, str)
            and type_ in {'string', 'grapheme', 'char'}
        )

    def _object_allocation(self, loc: Span, size: int, *, arena: bool = False) -> hir.FunctionCall:
        if arena:
            # storage that outlives the frame: elements of growable arrays
            return self._arena_allocation(self._int64_literal(loc, size), loc)
        allocator = '__static_alloca__' if self.lowering_module_startup else '__alloca__'
        return self._intrinsic_call(
            allocator,
            [self._int64_literal(loc, size)],
            'int64',
            loc,
        )

    def _field_address(self, base: hir.AST, offset: int, loc: Span) -> hir.AST:
        if offset == 0:
            return replace(base, type='int64')
        return self._int64_binary(
            '__add__',
            replace(base, type='int64'),
            self._int64_literal(loc, offset),
            loc,
        )

    def _object_copy(
        self,
        dest: hir.AST,
        src: hir.AST,
        object_type: ty.ObjectType,
        loc: Span,
        *,
        arena: bool = False,
    ) -> list[hir.AST]:
        """Copy every field; with ``arena``, nested mutable storage is arena-backed too."""
        _size, offsets = self._object_layout(object_type, dest)
        statements: list[hir.AST] = []
        for field in object_type.fields:
            dest_addr = self._field_address(dest, offsets[field.name], loc)
            src_addr = self._field_address(src, offsets[field.name], loc)
            members = self._field_union_members(field.type)
            if members is not None:
                statements.extend(self._union_copy_cell(dest_addr, src_addr, members, loc, prepared=False))
            elif isinstance(field.type, ty.ObjectType):
                statements.extend(self._object_copy(dest_addr, src_addr, field.type, loc, arena=arena))
            elif isinstance(field.type, ty.ArrayType):
                source = self._value_load(src_addr, field.type, loc)
                prelude, copied = self._clone_array_value(
                    replace(source, type='int64'),
                    field.type,
                    arena=arena,
                )
                statements.extend(prelude)
                statements.extend(
                    self._value_store(copied, dest_addr, field.type, loc)
                )
            elif isinstance(field.type, ty.FunctionType):
                loaded = self._intrinsic_call(
                    '__load_i64__',
                    [src_addr],
                    'int64',
                    loc,
                )
                statements.append(
                    self._intrinsic_call(
                        '__store_i64__',
                        [loaded, dest_addr],
                        ty.VOID_TYPE,
                        loc,
                    )
                )
            else:
                loaded = self._value_load(src_addr, field.type, loc)
                statements.extend(self._value_store(loaded, dest_addr, field.type, loc))
        return statements

    def _extract_object_literal(
        self,
        node: hir.ObjectLiteral,
        dest: hir.ExpressedIdentifier | None = None,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        if not isinstance(node.type, ty.ObjectType):
            self._target_error(node, 'object literal does not have an object type')
        size, offsets = self._object_layout(node.type, node)
        statements: list[hir.AST] = []
        if dest is None:
            dest = self._new_object_temp(node.loc)
            statements.append(
                hir.Declare(
                    node.loc,
                    ty.VOID_TYPE,
                    'let',
                    dest.name,
                    'int64',
                    self._object_allocation(node.loc, size),
                )
            )
        statements.extend(self._initialize_object_fields(node, dest, offsets))
        return statements, dest

    def _init_object_literal_at(
        self,
        node: hir.ObjectLiteral,
        dest: hir.AST,
    ) -> tuple[list[hir.AST], hir.AST]:
        if not isinstance(node.type, ty.ObjectType):
            self._target_error(node, 'object literal does not have an object type')
        _size, offsets = self._object_layout(node.type, node)
        return self._initialize_object_fields(node, dest, offsets), dest

    def _initialize_object_fields(
        self,
        node: hir.ObjectLiteral,
        dest: hir.AST,
        offsets: dict[str, int],
    ) -> list[hir.AST]:
        assert isinstance(node.type, ty.ObjectType)
        field_names = {
            field.binding_id: field.name
            for field in node.fields
            if field.binding_id is not None
        }
        self.object_literal_contexts.append((dest, node.type, field_names))
        statements: list[hir.AST] = []
        try:
            for field in node.fields:
                address = self._field_address(dest, offsets[field.name], field.loc)
                expected = node.type.field(field.name)
                field_type = expected.type if expected is not None else field.value.type
                members = self._field_union_members(field_type)
                if members is not None:
                    statements.extend(self._union_write(address, field.value, members, prepared=False))
                    continue
                if (
                    isinstance(field.value, hir.ObjectLiteral)
                    and isinstance(field_type, ty.ObjectType)
                ):
                    nested_prelude, _nested = self._init_object_literal_at(
                        field.value,
                        address,
                    )
                    statements.extend(nested_prelude)
                    continue
                if isinstance(field_type, ty.ArrayType):
                    prelude, value = self._independent_array_value(
                        field.value,
                        field_type,
                    )
                else:
                    prelude, value = self._extract_expression(field.value)
                statements.extend(prelude)
                statements.extend(
                    self._value_store(value, address, field_type, field.loc)
                )
        finally:
            self.object_literal_contexts.pop()
        return statements

    def _extract_object_pointer(
        self,
        node: hir.AST,
    ) -> tuple[list[hir.AST], hir.AST]:
        if isinstance(node, hir.ObjectLiteral):
            return self._extract_object_literal(node)
        if isinstance(node, hir.MemberAccess) and isinstance(node.type, ty.ObjectType):
            return self._extract_member_access(node)
        if isinstance(node, hir.FunctionCall) and isinstance(node.type, ty.ObjectType):
            return self._extract_expression(node)
        prelude, value = self._extract_expression(node)
        return prelude, value

    def _extract_member_access(
        self,
        node: hir.MemberAccess,
    ) -> tuple[list[hir.AST], hir.AST]:
        prelude, obj = self._extract_object_pointer(node.value)
        if not isinstance(node.value.type, ty.ObjectType):
            self._target_error(node, 'member access requires an object')
        _size, offsets = self._object_layout(node.value.type, node)
        address = self._field_address(obj, offsets[node.name], node.loc)
        field = node.value.type.field(node.name)
        field_type = field.type if field is not None else node.type
        if isinstance(field_type, ty.ObjectType):
            return prelude, address
        members = self._field_union_members(field_type)
        if members is not None:
            return prelude, self._union_field_read(address, members, node.type, node)
        return prelude, self._value_load(address, field_type, node.loc)

    def _union_field_read(
        self,
        cell: hir.AST,
        members: tuple[ty.TypeExpr, ...],
        static_type: ty.Type,
        node: hir.AST,
    ) -> hir.AST:
        """Read a union-typed field: the cell itself for a union view, else
        the payload of the member the checker narrowed the route to."""
        if isinstance(static_type, ty.TypeOr):
            return replace(cell, type='int64')
        system = ty.TypeSystem()
        member = next((m for m in members if system.is_subtype(static_type, m)), None)
        if member is None or member == 'undefined':
            self._target_error(node, 'a union field read of this type')
        return self._optional_load_payload(replace(cell, type='int64'), member, node.loc)

    def _extract_object_field_identifier(
        self,
        node: hir.ExpressedIdentifier,
    ) -> tuple[list[hir.AST], hir.AST]:
        if self.current_object_receiver is None or self.current_object_type is None:
            self._target_error(node, 'object field capture without a receiver')
        name = self.current_object_field_names[node.binding_id]
        _size, offsets = self._object_layout(self.current_object_type, node)
        address = self._field_address(self.current_object_receiver, offsets[name], node.loc)
        field = self.current_object_type.field(name)
        field_type = field.type if field is not None else node.type
        if isinstance(field_type, ty.ObjectType):
            return [], address
        members = self._field_union_members(field_type)
        if members is not None:
            return [], self._union_field_read(address, members, node.type, node)
        return [], self._value_load(address, field_type, node.loc)

    def _extract_literal_field_identifier(
        self,
        node: hir.ExpressedIdentifier,
        base: hir.AST,
        object_type: ty.ObjectType,
        name: str,
    ) -> tuple[list[hir.AST], hir.AST]:
        _size, offsets = self._object_layout(object_type, node)
        address = self._field_address(base, offsets[name], node.loc)
        field = object_type.field(name)
        field_type = field.type if field is not None else node.type
        if isinstance(field_type, ty.ObjectType):
            return [], address
        members = self._field_union_members(field_type)
        if members is not None:
            return [], self._union_field_read(address, members, node.type, node)
        return [], self._value_load(address, field_type, node.loc)

    def _is_object_method_func(self, func: hir.AST) -> bool:
        if isinstance(func, hir.MemberAccess) and isinstance(func.type, ty.FunctionType):
            return True
        return (
            isinstance(func, hir.ExpressedIdentifier)
            and func.binding_id is not None
            and func.binding_id in self.current_object_field_ids
            and isinstance(func.type, ty.FunctionType)
        )

    def _method_runtime_type(self, type_: ty.FunctionType) -> ty.FunctionType:
        lowered = self._lower_callable_type(type_)
        assert isinstance(lowered, ty.FunctionType)
        return replace(
            lowered,
            pos_or_kw=[ty.PosOrKwArg(None, 'int64'), *lowered.pos_or_kw],
        )

    def _extract_method_call(
        self,
        node: hir.FunctionCall,
    ) -> tuple[list[hir.AST], hir.AST]:
        func = node.func
        if isinstance(func, hir.MemberAccess):
            if not isinstance(func.value.type, ty.ObjectType):
                self._target_error(node, 'method call requires an object')
            obj_prelude, obj = self._extract_object_pointer(func.value)
            object_type = func.value.type
            name = func.name
            function_type = func.type
        else:
            if self.current_object_receiver is None or self.current_object_type is None:
                self._target_error(node, 'object method call without a receiver')
            obj_prelude, obj = [], self.current_object_receiver
            object_type = self.current_object_type
            assert isinstance(func, hir.ExpressedIdentifier) and func.binding_id is not None
            name = self.current_object_field_names[func.binding_id]
            function_type = func.type
        if not isinstance(function_type, ty.FunctionType):
            self._target_error(node, 'object method is not a function')
        _size, offsets = self._object_layout(object_type, node)
        loaded = hir.Transmute(
            func.loc,
            self._method_runtime_type(function_type),
            self._intrinsic_call(
                '__load_i64__',
                [self._field_address(obj, offsets[name], func.loc)],
                'int64',
                func.loc,
            ),
        )
        prelude = [*obj_prelude]
        pos_args: list[hir.AST] = [replace(obj, type='int64')]
        place_postlude: list[hir.AST] = []
        optional_arguments = self.call_optional_args.get(id(node), [])
        for index, arg in enumerate(node.pos_args):
            expected_type = (
                function_type.pos_or_kw[index].type
                if index < len(function_type.pos_or_kw)
                else None
            )
            payload = (
                optional_arguments[index]
                if index < len(optional_arguments)
                else ty.optional_payload(expected_type)
                if expected_type is not None
                else None
            )
            if isinstance(arg, hir.Place):
                arg_prelude, lowered_arg, arg_postlude = (
                    self._materialize_place_argument(arg)
                )
                place_postlude.extend(arg_postlude)
            elif payload is not None:
                arg_prelude, lowered_arg = self._materialize_optional(arg, payload)
            elif isinstance(arg.type, ty.ObjectType) or isinstance(expected_type, ty.ObjectType):
                arg_prelude, lowered_arg = self._extract_object_pointer(arg)
            else:
                arg_prelude, lowered_arg = self._extract_expression(arg)
            prelude.extend(arg_prelude)
            pos_args.append(lowered_arg)
        kw_args: dict[str, hir.AST] = {}
        optional_kwargs = self.call_optional_kwargs.get(id(node), {})
        for name, arg in node.kw_args.items():
            payload = optional_kwargs.get(name)
            if isinstance(arg, hir.Place):
                arg_prelude, lowered_arg, arg_postlude = (
                    self._materialize_place_argument(arg)
                )
                place_postlude.extend(arg_postlude)
            elif payload is not None:
                arg_prelude, lowered_arg = self._materialize_optional(arg, payload)
            elif isinstance(arg.type, ty.ObjectType):
                arg_prelude, lowered_arg = self._extract_object_pointer(arg)
            else:
                arg_prelude, lowered_arg = self._extract_expression(arg)
            prelude.extend(arg_prelude)
            kw_args[name] = lowered_arg
        if isinstance(node.type, ty.ObjectType):
            call_prelude, result = self._finish_object_call(
                node,
                loaded,
                pos_args,
                kw_args,
                prelude,
            )
            return [*call_prelude, *place_postlude], result
        if isinstance(node.type, ty.ArrayType) and node.type.length is not None:
            call_prelude, result = self._finish_array_call(
                node,
                loaded,
                pos_args,
                kw_args,
                prelude,
            )
            return [*call_prelude, *place_postlude], result
        result_payload = ty.optional_payload(node.type)
        if result_payload is not None:
            result = hir.ExpressedIdentifier(
                node.loc,
                'int64',
                self._new_optional_name('result_value'),
            )
            prelude.append(
                hir.Declare(
                    node.loc,
                    ty.VOID_TYPE,
                    'let',
                    result.name,
                    'int64',
                    self._optional_allocation(node.loc),
                )
            )
            prelude.append(
                replace(
                    node,
                    type=ty.VOID_TYPE,
                    func=loaded,
                    pos_args=[*pos_args, result],
                    kw_args=kw_args,
                )
            )
            return [*prelude, *place_postlude], replace(result, type=node.type)
        call = replace(node, func=loaded, pos_args=pos_args, kw_args=kw_args)
        return self._finish_scalar_call_place_writebacks(
            call,
            prelude,
            place_postlude,
        )

    def _finish_object_call(
        self,
        node: hir.FunctionCall,
        func: hir.AST,
        pos_args: list[hir.AST],
        kw_args: dict[str, hir.AST],
        prelude: list[hir.AST],
    ) -> tuple[list[hir.AST], hir.AST]:
        if not isinstance(node.type, ty.ObjectType):
            self._target_error(node, 'object call result is not an object')
        result = self.object_result_destinations.pop(id(node), None)
        if result is None:
            allocation, result = self._allocate_object_result_value(
                node.type,
                node.loc,
            )
            prelude.extend(allocation)
        prelude.append(
            replace(
                node,
                type=ty.VOID_TYPE,
                func=func,
                pos_args=[*pos_args, replace(result, type='int64')],
                kw_args=kw_args,
            )
        )
        return prelude, result

    def _lower_object_declare(
        self,
        node: hir.Declare,
        object_type: ty.ObjectType,
    ) -> list[hir.AST]:
        if isinstance(node.expr, (hir.ObjectLiteral, hir.FunctionCall)):
            prelude, ptr = self._extract_expression(node.expr)
            return [
                *prelude,
                replace(
                    node,
                    decltype='let',
                    annotation='int64',
                    expr=ptr,
                ),
            ]
        size, _offsets = self._object_layout(object_type, node)
        cell = hir.ExpressedIdentifier(
            node.loc,
            'int64',
            node.name,
            binding_id=node.binding_id,
        )
        declaration = replace(
            node,
            decltype='let',
            annotation='int64',
            expr=self._object_allocation(node.loc, size),
        )
        prelude, src = self._extract_object_pointer(node.expr)
        return [declaration, *prelude, *self._object_copy(cell, src, object_type, node.loc)]

    def _lower_object_assign(self, node: hir.Assign) -> list[hir.AST]:
        if node.op != '=':
            self._target_error(node, f'object compound assignment `{node.op}`')
        if not isinstance(node.target.type, ty.ObjectType):
            self._target_error(node, 'object assignment requires an object')
        dest = replace(node.target, type='int64')
        statements: list[hir.AST] = []
        binding = (
            self.binding_by_semantic_id.get(node.target.binding_id)
            if node.target.binding_id is not None
            else None
        )
        if (
            self.lowering_module_startup
            and binding is not None
            and binding.owner_function is None
            and node.target.binding_id is not None
            and node.target.binding_id not in self.object_globals_initialized
        ):
            size, _offsets = self._object_layout(node.target.type, node)
            statements.append(
                hir.Assign(
                    node.loc,
                    ty.VOID_TYPE,
                    dest,
                    '=',
                    self._object_allocation(node.loc, size),
                )
            )
            self.object_globals_initialized.add(node.target.binding_id)
        prelude, src = self._extract_object_pointer(node.value)
        statements.extend(prelude)
        statements.extend(self._object_copy(dest, src, node.target.type, node.loc))
        return statements

    def _lower_object_field_assign(self, node: hir.Assign) -> list[hir.AST]:
        if self.current_object_receiver is None or self.current_object_type is None:
            self._target_error(node, 'object field assignment without a receiver')
        assert node.target.binding_id is not None
        name = self.current_object_field_names[node.target.binding_id]
        _size, offsets = self._object_layout(self.current_object_type, node)
        address = self._field_address(
            self.current_object_receiver,
            offsets[name],
            node.loc,
        )
        field = self.current_object_type.field(name)
        field_type = field.type if field is not None else node.target.type
        if isinstance(field_type, ty.ObjectType):
            if node.op != '=':
                self._target_error(node, f'object field compound assignment `{node.op}`')
            prelude, src = self._extract_object_pointer(node.value)
            return [*prelude, *self._object_copy(address, src, field_type, node.loc)]
        if isinstance(field_type, ty.ArrayType) and node.op == '=':
            prelude, value = self._independent_array_value(
                node.value,
                field_type,
            )
            return [
                *prelude,
                *self._value_store(value, address, field_type, node.loc),
            ]
        assigned_value = node.value
        if node.op != '=':
            symbol = node.op[:-1]
            dunder = builtins.BINOP_DUNDER_MAP.get(symbol)
            if dunder is None:
                self._target_error(node, f'object field compound assignment `{node.op}`')
            function_type = ty.FunctionType(
                [
                    ty.PosOrKwArg('left', field_type),
                    ty.PosOrKwArg('right', field_type),
                ],
                [],
                None,
                field_type,
                [],
            )
            assigned_value = hir.FunctionCall(
                node.loc,
                field_type,
                hir.ExpressedIdentifier(node.loc, function_type, dunder),
                [
                    self._value_load(address, field_type, node.loc),
                    node.value,
                ],
                {},
            )
        prelude, value = self._extract_expression(assigned_value)
        return [*prelude, *self._value_store(value, address, field_type, node.loc)]

    def _lower_member_assign(self, node: hir.MemberAssign) -> list[hir.AST]:
        prelude, obj = self._extract_object_pointer(node.target.value)
        if not isinstance(node.target.value.type, ty.ObjectType):
            self._target_error(node, 'member assignment requires an object')
        _size, offsets = self._object_layout(node.target.value.type, node)
        address = self._field_address(obj, offsets[node.target.name], node.loc)
        field = node.target.value.type.field(node.target.name)
        field_type = field.type if field is not None else node.target.type
        members = self._field_union_members(field_type)
        if members is not None:
            return [*prelude, *self._union_write(address, node.value, members, prepared=False)]
        if isinstance(field_type, ty.ObjectType):
            value_prelude, src = self._extract_object_pointer(node.value)
            return [
                *prelude,
                *value_prelude,
                *self._object_copy(address, src, field_type, node.loc),
            ]
        if isinstance(field_type, ty.ArrayType):
            value_prelude, value = self._independent_array_value(
                node.value,
                field_type,
            )
        else:
            value_prelude, value = self._extract_expression(node.value)
        return [*prelude, *value_prelude, *self._value_store(value, address, field_type, node.loc)]

    def _object_result_write(self, item: hir.AST) -> list[hir.AST]:
        if self.current_object_result is None:
            raise TypeError('INTERNAL ERROR: missing object result cell')
        object_type = self.current_object_result.type
        if not isinstance(object_type, ty.ObjectType):
            raise TypeError('INTERNAL ERROR: object result is not an object type')
        dest = replace(self.current_object_result, type='int64')
        return [
            *self._write_object_result_value(dest, item, object_type),
            hir.Return(item.loc, ty.BOTTOM_TYPE, hir.Void(item.loc, ty.VOID_TYPE)),
        ]

    def _write_object_result_value(
        self,
        dest: hir.AST,
        item: hir.AST,
        object_type: ty.ObjectType,
    ) -> list[hir.AST]:
        """Write an object into a complete storage tree owned by the caller."""

        if isinstance(item, hir.FunctionCall):
            destination_prelude, destination = self._result_destination_identifier(
                dest,
                object_type,
                item.loc,
                object_result=True,
            )
            self.object_result_destinations[id(item)] = destination
            prelude, result = self._extract_expression(item)
            if id(item) in self.object_result_destinations:
                del self.object_result_destinations[id(item)]
                raise TypeError(
                    'INTERNAL ERROR: object result destination was not consumed'
                )
            if (
                not isinstance(result, hir.ExpressedIdentifier)
                or result.name != destination.name
            ):
                raise TypeError(
                    'INTERNAL ERROR: forwarded object result changed destination'
                )
            return [*destination_prelude, *prelude]
        if isinstance(item, hir.ObjectLiteral):
            return self._write_object_literal_result(dest, item, object_type)
        prelude, source = self._extract_object_pointer(item)
        return [
            *prelude,
            *self._copy_object_into_result_storage(
                dest,
                source,
                object_type,
                item.loc,
            ),
        ]

    def _write_object_literal_result(
        self,
        dest: hir.AST,
        node: hir.ObjectLiteral,
        object_type: ty.ObjectType,
    ) -> list[hir.AST]:
        """Initialize an object literal without replacing prepared child storage."""

        _size, offsets = self._object_layout(object_type, node)
        field_names = {
            field.binding_id: field.name
            for field in node.fields
            if field.binding_id is not None
        }
        self.object_literal_contexts.append((dest, object_type, field_names))
        statements: list[hir.AST] = []
        try:
            for field in node.fields:
                expected = object_type.field(field.name)
                field_type = expected.type if expected is not None else field.value.type
                address = self._field_address(dest, offsets[field.name], field.loc)
                members = self._field_union_members(field_type)
                if members is not None:
                    statements.extend(self._union_write(address, field.value, members, prepared=False))
                elif isinstance(field_type, ty.ArrayType) and field_type.length is None:
                    prelude, handle = self._arena_array_field_value(field.value, field_type)
                    statements.extend(prelude)
                    statements.extend(self._value_store(handle, address, field_type, field.loc))
                elif isinstance(field_type, ty.ArrayType):
                    nested_dest = self._value_load(
                        address,
                        field_type,
                        field.loc,
                    )
                    statements.extend(
                        self._write_array_result_value(
                            nested_dest,
                            field.value,
                            field_type,
                        )
                    )
                elif isinstance(field_type, ty.ObjectType):
                    statements.extend(
                        self._write_object_result_value(
                            address,
                            field.value,
                            field_type,
                        )
                    )
                else:
                    prelude, value = self._extract_expression(field.value)
                    statements.extend(prelude)
                    statements.extend(
                        self._value_store(value, address, field_type, field.loc)
                    )
        finally:
            self.object_literal_contexts.pop()
        return statements

    def _arena_array_field_value(
        self,
        node: hir.AST,
        array_type: ty.ArrayType,
    ) -> tuple[list[hir.AST], hir.AST]:
        """An arena-backed array handle for a runtime-length field of a result."""
        source = self._copy_source_expression(node)
        if (
            isinstance(source, hir.FunctionCall)
            and isinstance(source.type, ty.ArrayType)
            and source.type.length is None
        ):
            # a runtime-length call result is already arena-backed
            return self._extract_expression(node)
        return self._clone_dynamic_array_value(node, array_type, arena=True)

    def _copy_object_into_result_storage(
        self,
        dest: hir.AST,
        src: hir.AST,
        object_type: ty.ObjectType,
        loc: Span,
    ) -> list[hir.AST]:
        """Recursively copy an object into already-prepared mutable storage."""

        _size, offsets = self._object_layout(
            object_type,
            hir.Void(loc, ty.VOID_TYPE),
        )
        statements: list[hir.AST] = []
        for field in object_type.fields:
            dest_address = self._field_address(dest, offsets[field.name], loc)
            source_address = self._field_address(src, offsets[field.name], loc)
            members = self._field_union_members(field.type)
            if members is not None:
                statements.extend(self._union_copy_cell(dest_address, source_address, members, loc, prepared=False))
            elif isinstance(field.type, ty.ArrayType) and field.type.length is None:
                source_array = self._value_load(source_address, field.type, loc)
                prelude, copied = self._clone_dynamic_array_value(
                    replace(source_array, type='int64'), field.type, arena=True,
                )
                statements.extend(prelude)
                statements.extend(self._value_store(copied, dest_address, field.type, loc))
            elif isinstance(field.type, ty.ArrayType):
                target_array = self._value_load(dest_address, field.type, loc)
                source_array = self._value_load(source_address, field.type, loc)
                statements.extend(
                    self._copy_array_into_result_storage(
                        target_array,
                        source_array,
                        field.type,
                        loc,
                        source_is_pointer=True,
                    )
                )
            elif isinstance(field.type, ty.ObjectType):
                statements.extend(
                    self._copy_object_into_result_storage(
                        dest_address,
                        source_address,
                        field.type,
                        loc,
                    )
                )
            else:
                value = self._value_load(source_address, field.type, loc)
                statements.extend(
                    self._value_store(value, dest_address, field.type, loc)
                )
        return statements

