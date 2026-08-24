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
        return (
            member == 'undefined'
            or member == 'bool'
            or ty.fixed_integer_layout(member) is not None
            or isinstance(member, (ty.StringType, ty.StringLiteralType))
            or member in {'string', 'grapheme', 'char'}
        )

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
            # Same-union copy: move both cell words.
            prelude, source = self._extract_expression(value)
            source_word = (
                replace(source, type='int64')
                if isinstance(source, hir.ExpressedIdentifier)
                else source
            )
            tag = self._optional_tag(source_word, value.loc)
            payload_word = self._intrinsic_call(
                '__load_i64__',
                [self._optional_payload_address(source_word, value.loc)],
                'int64',
                value.loc,
            )
            return [
                *prelude,
                self._intrinsic_call(
                    '__store_u8__', [tag, cell], ty.VOID_TYPE, value.loc
                ),
                self._intrinsic_call(
                    '__store_i64__',
                    [
                        payload_word,
                        self._optional_payload_address(cell, value.loc),
                    ],
                    ty.VOID_TYPE,
                    value.loc,
                ),
            ]
        if isinstance(value.type, ty.TypeOr):
            self._target_error(
                value,
                'retagging between differently shaped union types',
            )
        index = self._union_member_index(members, value.type, value)
        member = members[index]
        prelude, payload_value = self._extract_expression(value)
        return [
            *prelude,
            tag_store(index),
            self._optional_store_payload(payload_value, cell, member, value.loc),
        ]

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

