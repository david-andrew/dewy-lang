"""Optional-value lowering: tag/payload cells and optional flows.

Split from ``lower.py``; methods run as part of ``_Lowerer``.
"""

from __future__ import annotations

from dataclasses import replace

from ...parser import t0
from ...reporting import Span
from ...semantic import hir, ty


class _OptionalLowering:
    def _optional_allocation(self, loc: Span) -> hir.FunctionCall:
        allocator = '__static_alloca__' if self.lowering_module_startup else '__alloca__'
        return self._intrinsic_call(
            allocator,
            [self._int64_literal(loc, 16)],
            'int64',
            loc,
        )

    def _optional_payload_address(self, cell: hir.AST, loc: Span) -> hir.AST:
        return self._int64_binary(
            '__add__',
            cell,
            self._int64_literal(loc, 8),
            loc,
        )

    @staticmethod
    def _uint8_literal(loc: Span, value: int) -> hir.Integer:
        return hir.Integer(loc, 'uint8', t0.base10, value)

    def _optional_tag(self, cell: hir.AST, loc: Span) -> hir.FunctionCall:
        return self._intrinsic_call('__load_u8__', [cell], 'uint8', loc)

    def _optional_store_payload(
        self,
        value: hir.AST,
        cell: hir.AST,
        payload: ty.TypeExpr,
        loc: Span,
    ) -> hir.FunctionCall:
        address = self._optional_payload_address(cell, loc)
        if payload == 'bool':
            value = hir.Transmute(value.loc, 'uint8', value)
            return self._intrinsic_call('__store_u8__', [value, address], ty.VOID_TYPE, loc)
        layout = ty.fixed_integer_layout(payload)
        if layout is not None:
            width, signed = layout
            prefix = 'i' if signed else 'u'
            return self._intrinsic_call(
                f'__store_{prefix}{width}__',
                [value, address],
                ty.VOID_TYPE,
                loc,
            )
        if isinstance(payload, ty.FunctionType):
            value = hir.Transmute(value.loc, 'int64', value)
        return self._intrinsic_call('__store_i64__', [value, address], ty.VOID_TYPE, loc)

    def _optional_load_payload(
        self,
        cell: hir.AST,
        payload: ty.TypeExpr,
        loc: Span,
    ) -> hir.AST:
        address = self._optional_payload_address(cell, loc)
        if payload == 'bool':
            loaded = self._intrinsic_call('__load_i8__', [address], 'int8', loc)
            return hir.Transmute(loc, 'bool', loaded)
        layout = ty.fixed_integer_layout(payload)
        if layout is not None:
            width, signed = layout
            prefix = 'i' if signed else 'u'
            return self._intrinsic_call(
                f'__load_{prefix}{width}__',
                [address],
                payload,
                loc,
            )
        loaded = self._intrinsic_call('__load_i64__', [address], 'int64', loc)
        if isinstance(payload, ty.FunctionType):
            return hir.Transmute(
                loc,
                self._lower_callable_type(payload),
                loaded,
            )
        # a handle member's payload is the object pointer, typed by the unfolded alias
        return replace(loaded, type=ty.unfold(payload))

    def _optional_write(
        self,
        cell: hir.AST,
        value: hir.AST,
        payload: ty.TypeExpr,
    ) -> list[hir.AST]:
        if isinstance(value, hir.ValueCast):
            return self._optional_write(cell, value.expr, payload)
        if isinstance(payload, ty.NamedType):
            # `Node | undefined`: the payload is a handle, deep-copied on every
            # store, exactly as in a general union cell (the tags coincide)
            return self._union_write(cell, value, ('undefined', payload), prepared=False)
        if isinstance(value, hir.Flow):
            prelude, flow = self._lower_optional_flow(value, cell, payload)
            return [*prelude, flow]
        def tag_store(tag: int) -> hir.FunctionCall:
            return self._intrinsic_call(
                '__store_u8__',
                [self._uint8_literal(value.loc, tag), cell],
                ty.VOID_TYPE,
                value.loc,
            )
        if isinstance(value, hir.Undefined):
            zero = self._int64_literal(value.loc, 0)
            return [
                tag_store(0),
                self._intrinsic_call(
                    '__store_i64__',
                    [zero, self._optional_payload_address(cell, value.loc)],
                    ty.VOID_TYPE,
                    value.loc,
                ),
            ]
        if ty.optional_payload(value.type) is not None:
            prelude, source = self._extract_expression(value)
            tag = self._optional_tag(source, value.loc)
            payload_value = self._optional_load_payload(source, payload, value.loc)
            return [
                *prelude,
                self._intrinsic_call('__store_u8__', [tag, cell], ty.VOID_TYPE, value.loc),
                self._optional_store_payload(payload_value, cell, payload, value.loc),
            ]
        prelude, payload_value = self._extract_expression(value)
        return [
            *prelude,
            tag_store(1),
            self._optional_store_payload(payload_value, cell, payload, value.loc),
        ]

    def _lower_optional_flow(
        self,
        node: hir.Flow,
        cell: hir.AST,
        payload: ty.TypeExpr,
    ) -> tuple[list[hir.AST], hir.Flow]:
        prelude: list[hir.AST] = []
        arms: list[hir.IfArm | hir.LoopArm] = []
        for index, arm in enumerate(node.arms):
            condition_prelude, condition = self._prepare_condition(arm.condition)
            if condition_prelude:
                if isinstance(arm, hir.LoopArm) or index > 0:
                    self._target_error(
                        arm.condition,
                        'optional flow condition requiring extracted statements',
                    )
                prelude.extend(condition_prelude)
            arms.append(
                replace(
                    arm,
                    condition=condition,
                    body=self._optional_flow_body(
                        arm.body,
                        cell,
                        payload,
                    ),
                )
            )
        default = (
            self._optional_flow_body(node.default, cell, payload)
            if node.default is not None
            else None
        )
        return prelude, replace(
            node,
            type=ty.VOID_TYPE,
            arms=arms,
            default=default,
        )

    def _optional_flow_body(
        self,
        body: hir.AST,
        cell: hir.AST,
        payload: ty.TypeExpr,
    ) -> hir.Block:
        if isinstance(body, hir.Block) and body.scoped:
            value_indices = [
                index
                for index, item in enumerate(body.items)
                if item.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
            ]
            if len(value_indices) != 1:
                self._target_error(body, 'optional branch does not have one value')
            statements: list[hir.AST] = []
            for index, item in enumerate(body.items):
                if index == value_indices[0]:
                    statements.extend(self._optional_write(cell, item, payload))
                else:
                    statements.extend(self._lower_statement(item))
            return replace(body, type=ty.VOID_TYPE, items=statements)
        return hir.Block(
            body.loc,
            ty.VOID_TYPE,
            self._optional_write(cell, body, payload),
            True,
        )

    def _materialize_optional(
        self,
        value: hir.AST,
        payload: ty.TypeExpr,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        if ty.optional_payload(value.type) is not None:
            prelude, cell = self._extract_expression(value)
            if isinstance(cell, hir.ExpressedIdentifier):
                return prelude, replace(cell, type='int64')
            target = hir.ExpressedIdentifier(
                value.loc,
                'int64',
                self._new_optional_name('value'),
            )
        else:
            target = hir.ExpressedIdentifier(
                value.loc,
                'int64',
                self._new_optional_name('value'),
            )
            prelude = []
        declaration = hir.Declare(
            value.loc,
            ty.VOID_TYPE,
            'let',
            target.name,
            'int64',
            self._optional_allocation(value.loc),
        )
        return [
            *prelude,
            declaration,
            *self._optional_write(target, value, payload),
        ], target

    def _new_optional_name(self, role: str) -> str:
        while True:
            name = f'__dewy_optional_{role}_{self.next_optional_temp}'
            self.next_optional_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

    # ------------------------------------------------------------------
    # General tagged unions share the optional cell layout: a one-byte tag
    # at offset 0 (the canonical member index; `undefined` is always 0 when
    # present, matching optional tags) and one payload word at offset 8.

    def _union_member_supported(self, member: ty.TypeExpr) -> bool:
        if isinstance(member, ty.NamedType):
            return True  # a recursive reference is always a handle member
        if ty.is_user_nominal(member):
            return True  # a unit-like error: tag only, zero payload
        if isinstance(member, ty.ObjectType):
            return self._object_result_fields_are_returnable(member)
        if isinstance(member, ty.ArrayType):
            return self._array_result_elements_are_returnable(member)
        return (
            member == 'undefined'
            or member == 'bool'
            or ty.fixed_integer_layout(member) is not None
            or isinstance(member, (ty.StringType, ty.StringLiteralType))
            or member in {'string', 'grapheme', 'char'}
        )

    # Aggregate members (fixed-layout objects and exact arrays) get a
    # prepared storage tree each, allocated with the cell and referenced from
    # slots after the payload word: [tag u8 @0][payload @8][tree slots @16..].
    # Tagging to an aggregate member copies the value into its tree and points
    # the payload word at the tree root.

    # A cell is *prepared* when it owns storage trees for its fixed-layout
    # aggregate members (locals, parameters, results). A cell stored inline in
    # an object field is unprepared: every aggregate member is a *handle* to
    # arena storage allocated when the member is tagged. Recursive references
    # (`ty.NamedType`) are handle members in every cell — that is what makes
    # `[value:int64 next:Node|undefined]` finite. Reads never care: the payload
    # word is the object pointer in both cases.

    @staticmethod
    def _union_member_kind(member: ty.TypeExpr, *, prepared: bool = True) -> str:
        if isinstance(member, ty.NamedType):
            return 'handle'
        if isinstance(member, (ty.ObjectType, ty.ArrayType)):
            return 'tree' if prepared else 'handle'
        return 'word'

    @classmethod
    def _union_tree_slots(cls, members: tuple[ty.TypeExpr, ...], *, prepared: bool = True) -> dict[int, int]:
        slots: dict[int, int] = {}
        offset = 16
        for index, member in enumerate(members):
            if cls._union_member_kind(member, prepared=prepared) == 'tree':
                slots[index] = offset
                offset += 8
        return slots

    def _union_source_pointer(self, cell: hir.AST, loc: Span) -> hir.AST:
        """The active aggregate member's object pointer: the payload word."""
        return self._intrinsic_call(
            '__load_i64__',
            [self._optional_payload_address(cell, loc)],
            'int64',
            loc,
        )

    def _union_handle_clone(
        self,
        source: hir.AST,
        member: ty.TypeExpr,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.AST]:
        """A fresh arena copy of the aggregate ``source`` points to, as a handle."""
        if isinstance(member, ty.NamedType):
            # recursion is dynamic: a synthesized function copies the alias
            return [], self._named_copy_call(member, source, loc)
        if isinstance(member, ty.ArrayType):
            return self._clone_dynamic_array_value(replace(source, type='int64'), member, arena=True)
        assert isinstance(member, ty.ObjectType)
        size, _offsets = self._object_layout(member, hir.Void(loc, ty.VOID_TYPE))
        dest = self._new_object_temp(loc)
        statements: list[hir.AST] = [
            hir.Declare(loc, ty.VOID_TYPE, 'let', dest.name, 'int64', self._arena_allocation(self._int64_literal(loc, size), loc)),
            *self._initialize_object_result_storage(dest, member, loc),
            *self._copy_object_into_result_storage(dest, replace(source, type='int64'), member, loc),
        ]
        return statements, dest

    def _union_handle_value(
        self,
        value: hir.AST,
        member: ty.TypeExpr,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.AST]:
        """Materialize ``value`` as arena storage of the member, as a handle."""
        unfolded = ty.unfold(member)
        if isinstance(unfolded, ty.ObjectType) and isinstance(value, hir.ObjectLiteral):
            size, _offsets = self._object_layout(unfolded, value)
            dest = self._new_object_temp(loc)
            statements: list[hir.AST] = [
                hir.Declare(loc, ty.VOID_TYPE, 'let', dest.name, 'int64', self._arena_allocation(self._int64_literal(loc, size), loc)),
                *self._initialize_object_result_storage(dest, unfolded, loc),
                *self._write_object_literal_result(dest, value, unfolded),
            ]
            return statements, dest
        if isinstance(unfolded, ty.ObjectType):
            prelude, source = self._extract_object_pointer(value)
            clone_prelude, handle = self._union_handle_clone(source, member, loc)
            return [*prelude, *clone_prelude], handle
        assert isinstance(unfolded, ty.ArrayType)
        return self._clone_dynamic_array_value(value, unfolded, arena=True)

    def _named_copy_call(self, named: ty.NamedType, source: hir.AST, loc: Span) -> hir.FunctionCall:
        symbol = self.named_copy_symbols.get(named.alias_id)
        if symbol is None:
            symbol = self._internal_symbol(f'__dewy_copy_{named.name}')
            self.named_copy_symbols[named.alias_id] = symbol
            self.pending_named_copies.append(named)
        function_type = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, 'int64')
        return hir.FunctionCall(
            loc,
            'int64',
            hir.ExpressedIdentifier(loc, function_type, symbol),
            [replace(source, type='int64')],
            {},
        )

    def _synthesize_named_copies(self) -> list:
        """Deep-copy functions for recursive aliases: `(src:int64):>int64`."""
        from .lowering_shared import LoweredFunction
        synthesized = []
        while self.pending_named_copies:
            named = self.pending_named_copies.pop(0)
            symbol = self.named_copy_symbols[named.alias_id]
            object_type = ty.unfold(named)
            assert isinstance(object_type, ty.ObjectType)
            loc = self.root.loc
            source = hir.ExpressedIdentifier(loc, 'int64', '__dewy_src')
            size, _offsets = self._object_layout(object_type, hir.Void(loc, ty.VOID_TYPE))
            dest = self._new_object_temp(loc)
            body = hir.Block(
                loc,
                ty.VOID_TYPE,
                [
                    hir.Declare(loc, ty.VOID_TYPE, 'let', dest.name, 'int64', self._arena_allocation(self._int64_literal(loc, size), loc)),
                    *self._initialize_object_result_storage(dest, object_type, loc),
                    *self._copy_object_into_result_storage(dest, source, object_type, loc),
                    hir.Return(loc, ty.BOTTOM_TYPE, dest),
                ],
                True,
            )
            function_type = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, 'int64')
            literal = hir.FunctionLiteral(
                loc,
                function_type,
                [hir.Param('__dewy_src', 'int64')],
                [],
                None,
                'int64',
                body,
            )
            synthesized.append(LoweredFunction(symbol, literal))
        return synthesized

    def _union_cell_allocation(
        self,
        members: tuple[ty.TypeExpr, ...],
        loc: Span,
    ) -> hir.FunctionCall:
        allocator = '__static_alloca__' if self.lowering_module_startup else '__alloca__'
        size = 16 + 8 * len(self._union_tree_slots(members))
        return self._intrinsic_call(
            allocator,
            [self._int64_literal(loc, size)],
            'int64',
            loc,
        )

    def _union_prepare_trees(
        self,
        cell: hir.AST,
        members: tuple[ty.TypeExpr, ...],
        loc: Span,
    ) -> list[hir.AST]:
        """Allocate the prepared storage tree of every aggregate member."""
        statements: list[hir.AST] = []
        for index, offset in self._union_tree_slots(members).items():
            member = members[index]
            if isinstance(member, ty.ObjectType):
                tree_statements, root = self._allocate_object_result_value(member, loc)
            else:
                assert isinstance(member, ty.ArrayType)
                tree_statements, root = self._allocate_array_result_value(member, loc)
            statements.extend(tree_statements)
            statements.append(
                self._intrinsic_call(
                    '__store_i64__',
                    [
                        replace(root, type='int64'),
                        self._int64_binary(
                            '__add__', cell, self._int64_literal(loc, offset), loc
                        ),
                    ],
                    ty.VOID_TYPE,
                    loc,
                )
            )
        return statements

    def _union_tree_root(
        self,
        cell: hir.AST,
        offset: int,
        member: ty.TypeExpr,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        root = hir.ExpressedIdentifier(loc, member, self._new_optional_name('tree'))
        declaration = hir.Declare(
            loc,
            ty.VOID_TYPE,
            'let',
            root.name,
            'int64',
            self._intrinsic_call(
                '__load_i64__',
                [self._int64_binary('__add__', cell, self._int64_literal(loc, offset), loc)],
                'int64',
                loc,
            ),
        )
        return [declaration], root

    def _union_copy_cell(
        self,
        dest: hir.AST,
        source: hir.AST,
        members: tuple[ty.TypeExpr, ...],
        loc: Span,
        *,
        prepared: bool = True,
    ) -> list[hir.AST]:
        """Copy a whole union cell, deep-copying an active aggregate member."""
        slots = self._union_tree_slots(members, prepared=prepared)
        aggregate_indexes = [
            index for index, member in enumerate(members)
            if self._union_member_kind(member, prepared=prepared) != 'word'
        ]
        tag = hir.ExpressedIdentifier(loc, 'uint8', self._new_optional_name('tag'))
        statements: list[hir.AST] = [
            hir.Declare(loc, ty.VOID_TYPE, 'let', tag.name, 'uint8', self._optional_tag(source, loc)),
            self._intrinsic_call('__store_u8__', [tag, dest], ty.VOID_TYPE, loc),
        ]
        word_copy = self._intrinsic_call(
            '__store_i64__',
            [
                self._intrinsic_call(
                    '__load_i64__',
                    [self._optional_payload_address(source, loc)],
                    'int64',
                    loc,
                ),
                self._optional_payload_address(dest, loc),
            ],
            ty.VOID_TYPE,
            loc,
        )
        if not aggregate_indexes:
            return [*statements, word_copy]
        arms: list[hir.IfArm | hir.LoopArm] = []
        for index in aggregate_indexes:
            member = members[index]
            body = self._union_aggregate_copy_into(dest, self._union_source_pointer(source, loc), member, slots.get(index), loc)
            arms.append(
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    self._typed_equality(tag, self._uint8_literal(loc, index), 'uint8', loc),
                    hir.Block(loc, ty.VOID_TYPE, body, True),
                )
            )
        statements.append(
            hir.Flow(loc, ty.VOID_TYPE, arms, hir.Block(loc, ty.VOID_TYPE, [word_copy], True))
        )
        return statements

    def _union_aggregate_copy_into(
        self,
        dest: hir.AST,
        source_pointer: hir.AST,
        member: ty.TypeExpr,
        slot: int | None,
        loc: Span,
    ) -> list[hir.AST]:
        """Copy the aggregate at ``source_pointer`` into ``dest``'s member storage
        (its prepared tree at ``slot``, else a fresh handle) and point the payload at it."""
        if slot is not None:
            dest_prelude, dest_root = self._union_tree_root(dest, slot, member, loc)
            source_root = hir.ExpressedIdentifier(loc, 'int64', self._new_optional_name('source'))
            source_prelude = [hir.Declare(loc, ty.VOID_TYPE, 'let', source_root.name, 'int64', source_pointer)]
            if isinstance(member, ty.ObjectType):
                copy = self._copy_object_into_result_storage(
                    replace(dest_root, type='int64'), source_root, member, loc,
                )
            else:
                assert isinstance(member, ty.ArrayType)
                copy = self._copy_array_into_result_storage(
                    replace(dest_root, type='int64'), source_root, member, loc, source_is_pointer=True,
                )
            handle: hir.AST = replace(dest_root, type='int64')
            prelude = [*dest_prelude, *source_prelude, *copy]
        else:
            source_root = hir.ExpressedIdentifier(loc, 'int64', self._new_optional_name('source'))
            clone_prelude, handle = self._union_handle_clone(source_root, member, loc)
            prelude = [
                hir.Declare(loc, ty.VOID_TYPE, 'let', source_root.name, 'int64', source_pointer),
                *clone_prelude,
            ]
        return [
            *prelude,
            self._intrinsic_call(
                '__store_i64__',
                [handle, self._optional_payload_address(dest, loc)],
                ty.VOID_TYPE,
                loc,
            ),
        ]

    def _union_member_index(
        self,
        members: tuple[ty.TypeExpr, ...],
        value_type: ty.TypeExpr,
        node: hir.AST,
    ) -> int:
        system = ty.TypeSystem()
        for index, member in enumerate(members):
            if system.is_subtype(value_type, member):
                return index
        self._target_error(
            node,
            'a union store whose member representation cannot be selected',
        )

    def _union_write(
        self,
        cell: hir.AST,
        value: hir.AST,
        members: tuple[ty.TypeExpr, ...],
        *,
        prepared: bool = True,
    ) -> list[hir.AST]:
        """Store one value into a union cell, tagging it by member index."""
        if isinstance(value, hir.ValueCast):
            return self._union_write(cell, value.expr, members, prepared=prepared)
        if (
            isinstance(value, hir.RepresentationCast)
            and ty.runtime_union_members(value.type) == members
        ):
            # Checking wraps member values in a conversion to the union type;
            # the tag-and-payload store below is that conversion.
            return self._union_write(cell, value.expr, members, prepared=prepared)
        if isinstance(value, hir.Flow):
            prelude, flow = self._lower_union_flow(value, cell, members, prepared=prepared)
            return [*prelude, flow]

        def tag_store(tag: int) -> hir.FunctionCall:
            return self._intrinsic_call(
                '__store_u8__',
                [self._uint8_literal(value.loc, tag), cell],
                ty.VOID_TYPE,
                value.loc,
            )

        if isinstance(value, hir.Undefined):
            index = self._union_member_index(members, 'undefined', value)
            zero = self._int64_literal(value.loc, 0)
            return [
                tag_store(index),
                self._intrinsic_call(
                    '__store_i64__',
                    [zero, self._optional_payload_address(cell, value.loc)],
                    ty.VOID_TYPE,
                    value.loc,
                ),
            ]
        if self._field_union_members(value.type) == members:
            # Same-union copy: tag, payload word, and the active aggregate tree.
            prelude, source = self._extract_expression(value)
            source_word = (
                replace(source, type='int64')
                if isinstance(source, hir.ExpressedIdentifier)
                else source
            )
            return [*prelude, *self._union_copy_cell(cell, source_word, members, value.loc, prepared=prepared)]
        source_members = self._field_union_members(value.type)
        if source_members is not None:
            if not all(member in members for member in source_members):
                self._target_error(
                    value,
                    'a union value whose members are not all members of the target union',
                )
            prelude, source = self._extract_expression(value)
            source_word = (
                replace(source, type='int64')
                if isinstance(source, hir.ExpressedIdentifier)
                else source
            )
            return [
                *prelude,
                *self._union_retag(cell, source_word, source_members, members, value.loc, prepared=prepared),
            ]
        if isinstance(value.type, ty.TypeOr):
            self._target_error(
                value,
                'retagging between differently shaped union types',
            )
        index = self._union_member_index(members, value.type, value)
        member = members[index]
        slots = self._union_tree_slots(members, prepared=prepared)
        if self._union_member_kind(member, prepared=prepared) == 'handle':
            handle_prelude, handle = self._union_handle_value(value, member, value.loc)
            return [
                *handle_prelude,
                tag_store(index),
                self._intrinsic_call(
                    '__store_i64__',
                    [replace(handle, type='int64'), self._optional_payload_address(cell, value.loc)],
                    ty.VOID_TYPE,
                    value.loc,
                ),
            ]
        if index in slots:
            root_prelude, root = self._union_tree_root(cell, slots[index], member, value.loc)
            if isinstance(member, ty.ObjectType):
                write = self._write_object_result_value(
                    replace(root, type='int64'), value, member
                )
            else:
                assert isinstance(member, ty.ArrayType)
                write = self._write_array_result_value(
                    replace(root, type='int64'), value, member
                )
            return [
                *root_prelude,
                *write,
                tag_store(index),
                self._intrinsic_call(
                    '__store_i64__',
                    [
                        replace(root, type='int64'),
                        self._optional_payload_address(cell, value.loc),
                    ],
                    ty.VOID_TYPE,
                    value.loc,
                ),
            ]
        prelude, payload_value = self._extract_expression(value)
        return [
            *prelude,
            tag_store(index),
            self._optional_store_payload(payload_value, cell, member, value.loc),
        ]

    def _union_retag(
        self,
        dest: hir.AST,
        source: hir.AST,
        source_members: tuple[ty.TypeExpr, ...],
        dest_members: tuple[ty.TypeExpr, ...],
        loc: Span,
        *,
        prepared: bool = True,
    ) -> list[hir.AST]:
        """Copy a union cell into a wider union, renumbering the tag."""
        dest_slots = self._union_tree_slots(dest_members, prepared=prepared)
        tag = hir.ExpressedIdentifier(loc, 'uint8', self._new_optional_name('tag'))
        statements: list[hir.AST] = [
            hir.Declare(loc, ty.VOID_TYPE, 'let', tag.name, 'uint8', self._optional_tag(source, loc)),
        ]
        arms: list[hir.IfArm | hir.LoopArm] = []
        for source_index, member in enumerate(source_members):
            dest_index = dest_members.index(member)
            body: list[hir.AST] = [
                self._intrinsic_call(
                    '__store_u8__',
                    [self._uint8_literal(loc, dest_index), dest],
                    ty.VOID_TYPE,
                    loc,
                ),
            ]
            if self._union_member_kind(member, prepared=prepared) != 'word':
                body.extend(
                    self._union_aggregate_copy_into(
                        dest, self._union_source_pointer(source, loc), member, dest_slots.get(dest_index), loc,
                    )
                )
            else:
                body.append(
                    self._intrinsic_call(
                        '__store_i64__',
                        [
                            self._intrinsic_call(
                                '__load_i64__',
                                [self._optional_payload_address(source, loc)],
                                'int64',
                                loc,
                            ),
                            self._optional_payload_address(dest, loc),
                        ],
                        ty.VOID_TYPE,
                        loc,
                    )
                )
            arms.append(
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    self._typed_equality(tag, self._uint8_literal(loc, source_index), 'uint8', loc),
                    hir.Block(loc, ty.VOID_TYPE, body, True),
                )
            )
        statements.append(hir.Flow(loc, ty.VOID_TYPE, arms, None))
        return statements

    def _lower_union_flow(
        self,
        node: hir.Flow,
        cell: hir.AST,
        members: tuple[ty.TypeExpr, ...],
        *,
        prepared: bool = True,
    ) -> tuple[list[hir.AST], hir.Flow]:
        prelude: list[hir.AST] = []
        arms: list[hir.IfArm | hir.LoopArm] = []
        for index, arm in enumerate(node.arms):
            condition_prelude, condition = self._prepare_condition(arm.condition)
            if condition_prelude:
                if isinstance(arm, hir.LoopArm) or index > 0:
                    self._target_error(
                        arm.condition,
                        'union flow condition requiring extracted statements',
                    )
                prelude.extend(condition_prelude)
            arms.append(
                replace(
                    arm,
                    condition=condition,
                    body=self._union_flow_body(arm.body, cell, members, prepared=prepared),
                )
            )
        default = (
            self._union_flow_body(node.default, cell, members, prepared=prepared)
            if node.default is not None
            else None
        )
        return prelude, replace(
            node,
            type=ty.VOID_TYPE,
            arms=arms,
            default=default,
        )

    def _materialize_union(
        self,
        value: hir.AST,
        members: tuple[ty.TypeExpr, ...],
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Produce a union cell pointer for one argument value."""
        if (
            isinstance(value, (hir.RepresentationCast, hir.ValueCast))
            and ty.runtime_union_members(value.type) == members
        ):
            return self._materialize_union(value.expr, members)
        if ty.runtime_union_members(value.type) == members:
            prelude, cell = self._extract_expression(value)
            if isinstance(cell, hir.ExpressedIdentifier):
                return prelude, replace(cell, type='int64')
            target = hir.ExpressedIdentifier(
                value.loc,
                'int64',
                self._new_optional_name('value'),
            )
            return [
                *prelude,
                hir.Declare(
                    value.loc,
                    ty.VOID_TYPE,
                    'let',
                    target.name,
                    'int64',
                    cell,
                ),
            ], target
        target = hir.ExpressedIdentifier(
            value.loc,
            'int64',
            self._new_optional_name('value'),
        )
        declaration = hir.Declare(
            value.loc,
            ty.VOID_TYPE,
            'let',
            target.name,
            'int64',
            self._union_cell_allocation(members, value.loc),
        )
        return [
            declaration,
            *self._union_prepare_trees(target, members, value.loc),
            *self._union_write(target, value, members),
        ], target

    def _union_result_write(self, item: hir.AST) -> list[hir.AST]:
        """Write one returned union value into the caller-owned result cell."""
        if self.current_union_result is None:
            raise TypeError('INTERNAL ERROR: missing union result cell')
        members = ty.runtime_union_members(self.current_union_result.type)
        if members is None:
            raise TypeError('INTERNAL ERROR: union result cell has no members')
        dest = replace(self.current_union_result, type='int64')
        return [
            *self._union_write(dest, item, members),
            hir.Return(item.loc, ty.BOTTOM_TYPE, hir.Void(item.loc, ty.VOID_TYPE)),
        ]

    def _union_flow_body(
        self,
        body: hir.AST,
        cell: hir.AST,
        members: tuple[ty.TypeExpr, ...],
        *,
        prepared: bool = True,
    ) -> hir.Block:
        if isinstance(body, hir.Block) and body.scoped:
            value_indices = [
                index
                for index, item in enumerate(body.items)
                if item.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
            ]
            if len(value_indices) != 1:
                self._target_error(body, 'union branch does not have one value')
            statements: list[hir.AST] = []
            for index, item in enumerate(body.items):
                if index == value_indices[0]:
                    statements.extend(self._union_write(cell, item, members, prepared=prepared))
                else:
                    statements.extend(self._lower_statement(item))
            return replace(body, type=ty.VOID_TYPE, items=statements)
        return hir.Block(
            body.loc,
            ty.VOID_TYPE,
            self._union_write(cell, body, members, prepared=prepared),
            True,
        )

