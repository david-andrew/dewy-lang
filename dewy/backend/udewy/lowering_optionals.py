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
        return replace(loaded, type=payload)

    def _optional_write(
        self,
        cell: hir.AST,
        value: hir.AST,
        payload: ty.TypeExpr,
    ) -> list[hir.AST]:
        if isinstance(value, hir.ValueCast):
            return self._optional_write(cell, value.expr, payload)
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

    @staticmethod
    def _union_tree_slots(members: tuple[ty.TypeExpr, ...]) -> dict[int, int]:
        slots: dict[int, int] = {}
        offset = 16
        for index, member in enumerate(members):
            if isinstance(member, (ty.ObjectType, ty.ArrayType)):
                slots[index] = offset
                offset += 8
        return slots

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
    ) -> list[hir.AST]:
        """Copy a whole union cell, deep-copying an active aggregate member."""
        slots = self._union_tree_slots(members)
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
        if not slots:
            return [*statements, word_copy]
        arms: list[hir.IfArm | hir.LoopArm] = []
        for index, offset in slots.items():
            member = members[index]
            dest_prelude, dest_root = self._union_tree_root(dest, offset, member, loc)
            source_prelude, source_root = self._union_tree_root(source, offset, member, loc)
            if isinstance(member, ty.ObjectType):
                copy = self._copy_object_into_result_storage(
                    replace(dest_root, type='int64'),
                    replace(source_root, type='int64'),
                    member,
                    loc,
                )
            else:
                assert isinstance(member, ty.ArrayType)
                copy = self._copy_array_into_result_storage(
                    replace(dest_root, type='int64'),
                    replace(source_root, type='int64'),
                    member,
                    loc,
                    source_is_pointer=True,
                )
            arms.append(
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    self._typed_equality(tag, self._uint8_literal(loc, index), 'uint8', loc),
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [
                            *dest_prelude,
                            *source_prelude,
                            *copy,
                            self._intrinsic_call(
                                '__store_i64__',
                                [
                                    replace(dest_root, type='int64'),
                                    self._optional_payload_address(dest, loc),
                                ],
                                ty.VOID_TYPE,
                                loc,
                            ),
                        ],
                        True,
                    ),
                )
            )
        statements.append(
            hir.Flow(loc, ty.VOID_TYPE, arms, hir.Block(loc, ty.VOID_TYPE, [word_copy], True))
        )
        return statements

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
    ) -> list[hir.AST]:
        """Store one value into a union cell, tagging it by member index."""
        if isinstance(value, hir.ValueCast):
            return self._union_write(cell, value.expr, members)
        if (
            isinstance(value, hir.RepresentationCast)
            and ty.runtime_union_members(value.type) == members
        ):
            # Checking wraps member values in a conversion to the union type;
            # the tag-and-payload store below is that conversion.
            return self._union_write(cell, value.expr, members)
        if isinstance(value, hir.Flow):
            prelude, flow = self._lower_union_flow(value, cell, members)
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
        if ty.runtime_union_members(value.type) == members:
            # Same-union copy: tag, payload word, and the active aggregate tree.
            prelude, source = self._extract_expression(value)
            source_word = (
                replace(source, type='int64')
                if isinstance(source, hir.ExpressedIdentifier)
                else source
            )
            return [*prelude, *self._union_copy_cell(cell, source_word, members, value.loc)]
        source_members = ty.runtime_union_members(value.type)
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
                *self._union_retag(cell, source_word, source_members, members, value.loc),
            ]
        if isinstance(value.type, ty.TypeOr):
            self._target_error(
                value,
                'retagging between differently shaped union types',
            )
        index = self._union_member_index(members, value.type, value)
        member = members[index]
        slots = self._union_tree_slots(members)
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
    ) -> list[hir.AST]:
        """Copy a union cell into a wider union, renumbering the tag."""
        source_slots = self._union_tree_slots(source_members)
        dest_slots = self._union_tree_slots(dest_members)
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
            if source_index in source_slots:
                dest_prelude, dest_root = self._union_tree_root(
                    dest, dest_slots[dest_index], member, loc
                )
                source_prelude, source_root = self._union_tree_root(
                    source, source_slots[source_index], member, loc
                )
                if isinstance(member, ty.ObjectType):
                    copy = self._copy_object_into_result_storage(
                        replace(dest_root, type='int64'),
                        replace(source_root, type='int64'),
                        member,
                        loc,
                    )
                else:
                    assert isinstance(member, ty.ArrayType)
                    copy = self._copy_array_into_result_storage(
                        replace(dest_root, type='int64'),
                        replace(source_root, type='int64'),
                        member,
                        loc,
                        source_is_pointer=True,
                    )
                body.extend([
                    *dest_prelude,
                    *source_prelude,
                    *copy,
                    self._intrinsic_call(
                        '__store_i64__',
                        [replace(dest_root, type='int64'), self._optional_payload_address(dest, loc)],
                        ty.VOID_TYPE,
                        loc,
                    ),
                ])
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
                    body=self._union_flow_body(arm.body, cell, members),
                )
            )
        default = (
            self._union_flow_body(node.default, cell, members)
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
                    statements.extend(self._union_write(cell, item, members))
                else:
                    statements.extend(self._lower_statement(item))
            return replace(body, type=ty.VOID_TYPE, items=statements)
        return hir.Block(
            body.loc,
            ty.VOID_TYPE,
            self._union_write(cell, body, members),
            True,
        )

