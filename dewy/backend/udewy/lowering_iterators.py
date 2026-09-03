"""Generic iterator flows: single and multi-iterator loops.

Split from ``lower.py``; methods run as part of ``_Lowerer``.
"""

from __future__ import annotations

from dataclasses import replace

from ...reporting import Error, Pointer
from ...semantic import hir, ty
from ...semantic.errors import NotImplementedYet
from .lowering_shared import (
    ARRAY_LENGTH_OFFSET,
    STRING_DESCRIPTOR_SIZE,
    STRING_GRAPHEME_LENGTH_OFFSET,
    ArrayRepresentation,
)


class _IteratorLowering:
    def _new_iterator_temp(
        self,
        node: hir.IteratorExpression,
    ) -> hir.ExpressedIdentifier:
        while True:
            name = f'__dewy_iterator_{self.next_iterator_temp}'
            self.next_iterator_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(node.loc, 'int64', name)

    def _new_iterator_name(self, role: str) -> str:
        while True:
            name = f'__dewy_iterator_{role}_{self.next_iterator_value}'
            self.next_iterator_value += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

    def _lower_iterator_flow(
        self,
        node: hir.Flow,
        arm: hir.LoopArm,
    ) -> list[hir.AST]:
        """Lower one range iterator to declarations and a counted udewy loop."""

        iterator = arm.condition
        if not isinstance(iterator, hir.IteratorExpression):
            raise TypeError('INTERNAL ERROR: iterator loop has no iterator condition')
        if isinstance(iterator.iterable.type, ty.ArrayType):
            return self._lower_array_iterator_flow(node, arm, iterator)
        if not isinstance(iterator.iterable, hir.Range):
            return self._lower_string_iterator_flow(node, arm, iterator)
        # a guarded counter (`loop i in 0.. and i <? n`, or `0..uint64.max`): the
        # body's guard ends the loop before the counter leaves the word
        unbounded = iterator.guarded and (iterator.count is None or not ty.integer_literal_fits(iterator.count, 'int64'))
        if not unbounded:
            self._require_finite_udewy_iterator(iterator)
        offset = self._new_iterator_temp(iterator)
        offset_declaration = hir.Declare(
            iterator.loc,
            ty.VOID_TYPE,
            'let',
            offset.name,
            'int64',
            self._int64_literal(iterator.loc, 0),
        )
        target_value = self._iterator_value(
            iterator,
            replace(offset, loc=iterator.loc),
        )
        if isinstance(iterator.target.type, ty.StringType):
            target_declarations, target_updates = self._string_iterator_target(
                iterator,
                target_value,
            )
        else:
            target_declarations = [
                hir.Declare(
                    iterator.target.loc,
                    ty.VOID_TYPE,
                    'let',
                    iterator.target.name,
                    'int64',
                    self._int64_literal(iterator.loc, iterator.first),
                    binding_id=iterator.target.binding_id,
                )
            ]
            target_updates = [
                hir.Assign(
                    iterator.loc,
                    ty.VOID_TYPE,
                    replace(iterator.target, loc=iterator.loc),
                    '=',
                    target_value,
                )
            ]
        increment = hir.Assign(
            iterator.loc,
            ty.VOID_TYPE,
            replace(offset, loc=iterator.loc),
            '+=',
            self._int64_literal(iterator.loc, 1),
        )
        lowered_body = self._lower_loop_body(arm)
        body_items = (
            lowered_body.items
            if isinstance(lowered_body, hir.Block)
            else [lowered_body]
        )
        body = hir.Block(
            arm.body.loc,
            ty.VOID_TYPE,
            [*target_updates, increment, *body_items],
            True,
        )
        if unbounded:
            condition: hir.AST = hir.Bool(iterator.loc, 'bool', True)
        else:
            condition = self._int64_comparison(
                '__lt__',
                replace(offset, loc=iterator.loc),
                self._int64_literal(iterator.loc, iterator.count),
                iterator.loc,
            )
        loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [hir.LoopArm(arm.loc, ty.VOID_TYPE, condition, body)],
            None,
        )
        return [offset_declaration, *target_declarations, loop]

    def _lower_multi_iterator_flow(
        self,
        node: hir.Flow,
        arm: hir.LoopArm,
    ) -> list[hir.AST]:
        condition = arm.condition
        if not isinstance(condition, hir.MultiIteratorExpression):
            raise TypeError('INTERNAL ERROR: multiiterator loop has no composite condition')
        for iterator in condition.iterators:
            if isinstance(iterator.iterable, hir.Range):
                self._require_finite_udewy_iterator(iterator)
        declarations: list[hir.AST] = []
        updates: list[hir.AST] = []
        active_values: list[hir.ExpressedIdentifier] = []
        for iterator in condition.iterators:
            range_iterator = isinstance(iterator.iterable, hir.Range)
            array_iterator = isinstance(iterator.iterable.type, ty.ArrayType)
            string_iterator = not range_iterator and not array_iterator
            string_value: hir.AST | None = None
            array_value: hir.AST | None = None
            array_representation: ArrayRepresentation | None = None
            if string_iterator:
                string_prelude, string_value = self._extract_expression(
                    iterator.iterable
                )
                declarations.extend(string_prelude)
            elif array_iterator:
                array_representation = self._array_use_representation(
                    iterator.iterable
                )
                array_prelude, array_value = self._extract_expression(
                    iterator.iterable
                )
                declarations.extend(array_prelude)
                if iterator.count is None and array_representation is not None:
                    self._target_error(
                        iterator.iterable,
                        'a raw-represented array iterated with a runtime length',
                    )
            else:
                assert iterator.count is not None
            offset = self._new_iterator_temp(iterator)
            offset_value = replace(offset, loc=iterator.loc)
            active = hir.ExpressedIdentifier(
                iterator.loc,
                'bool',
                self._new_iterator_name('active'),
            )
            active_values.append(active)
            declarations.extend([
                hir.Declare(
                    iterator.loc,
                    ty.VOID_TYPE,
                    'let',
                    offset.name,
                    'int64',
                    self._int64_literal(iterator.loc, 0),
                ),
                hir.Declare(
                    iterator.loc,
                    ty.VOID_TYPE,
                    'let',
                    active.name,
                    'bool',
                    hir.Bool(iterator.loc, 'bool', False),
                ),
            ])
            payload = ty.optional_payload(iterator.target.type)
            target = replace(iterator.target, loc=iterator.loc)
            semantic_target_type = payload or iterator.target.type
            runtime_target_type = self._lower_runtime_value_type(
                semantic_target_type
            )
            value_target: hir.AST = target
            if payload is not None:
                target = replace(target, type='int64')
                declarations.append(
                    hir.Declare(
                        iterator.loc,
                        ty.VOID_TYPE,
                        'let',
                        target.name,
                        'int64',
                        self._optional_allocation(iterator.loc),
                        binding_id=iterator.target.binding_id,
                    )
                )
                declarations.extend(
                    self._optional_write(
                        target,
                        hir.NoneValue(iterator.loc, 'none'),
                        payload,
                    )
                )
                if string_iterator:
                    value_target = hir.ExpressedIdentifier(
                        iterator.loc,
                        payload,
                        self._new_string_temp(
                            iterator.loc,
                            payload,
                            'iterator_value',
                        ).name,
                    )
                    declarations.append(
                        hir.Declare(
                            iterator.loc,
                            ty.VOID_TYPE,
                            'let',
                            value_target.name,
                            'int64',
                            self._intrinsic_call(
                                '__alloca__',
                                [self._int64_literal(
                                    iterator.loc,
                                    STRING_DESCRIPTOR_SIZE,
                                )],
                                'int64',
                                iterator.loc,
                            ),
                        )
                    )
            else:
                placeholder = (
                    self._int64_literal(iterator.loc, 0)
                    if array_iterator and runtime_target_type == 'int64'
                    else self._default_placeholder(
                        semantic_target_type,
                        iterator.loc,
                    )
                    if array_iterator
                    else self._int64_literal(
                        iterator.loc,
                        iterator.first,
                    )
                )
                declarations.append(
                    hir.Declare(
                        iterator.loc,
                        ty.VOID_TYPE,
                        'let',
                        target.name,
                        runtime_target_type,
                        (
                            self._intrinsic_call(
                                '__alloca__',
                                [
                                    self._int64_literal(
                                        iterator.loc,
                                        STRING_DESCRIPTOR_SIZE,
                                    )
                                ],
                                'int64',
                                iterator.loc,
                            )
                            if string_iterator
                            else placeholder
                        ),
                        binding_id=iterator.target.binding_id,
                    )
                )
                if string_iterator:
                    value_target = target
            active_limit = (
                self._load_i64_field(
                    string_value,
                    STRING_GRAPHEME_LENGTH_OFFSET,
                    iterator.loc,
                )
                if string_value is not None
                else self._int64_literal(iterator.loc, iterator.count)
                if array_value is not None and iterator.count is not None
                else self._load_i64_field(
                    replace(array_value, type='int64')
                    if isinstance(array_value, hir.ExpressedIdentifier)
                    else array_value,
                    ARRAY_LENGTH_OFFSET,
                    iterator.loc,
                )
                if array_value is not None
                else self._int64_literal(iterator.loc, iterator.count)
            )
            active_test = self._int64_comparison(
                '__lt__',
                offset_value,
                active_limit,
                iterator.loc,
            )
            updates.append(
                hir.Assign(
                    iterator.loc,
                    ty.VOID_TYPE,
                    replace(active, loc=iterator.loc),
                    '=',
                    active_test,
                )
            )
            if string_value is not None:
                value = value_target
                value_updates = self._string_iterator_view_updates(
                    string_value,
                    value_target,
                    offset_value,
                    iterator.loc,
                )
            elif array_value is not None:
                assert isinstance(iterator.iterable.type, ty.ArrayType)
                element_type = iterator.iterable.type.element
                element_bytes, _signed = self._array_element_layout(
                    element_type,
                    iterator,
                )
                address = (
                    self._pointer_element_address(
                        array_value,
                        offset_value,
                        element_bytes,
                        iterator.loc,
                    )
                    if array_representation is not None
                    else self._array_element_address(
                        array_value,
                        offset_value,
                        element_type,
                        iterator.loc,
                    )
                )
                value = self._array_load(address, element_type, iterator.loc)
                value_updates = []
            else:
                value = self._iterator_value(iterator, offset_value)
                value_updates = []
            if payload is not None and self._is_optional_element(element_type if array_value is not None else None):
                # the element word is a cell pointer: copy its tag and payload
                # into the target cell directly (the value is not re-wrapped)
                loc = iterator.loc
                pointer = hir.ExpressedIdentifier(loc, 'int64', self._new_iterator_name('cell'))
                defined_body = [
                    *value_updates,
                    hir.Declare(loc, ty.VOID_TYPE, 'let', pointer.name, 'int64', replace(value, type='int64') if isinstance(value, hir.ExpressedIdentifier) else value),
                    self._intrinsic_call('__store_i64__', [self._optional_tag(pointer, loc), target], ty.VOID_TYPE, loc),
                    self._intrinsic_call('__store_i64__', [self._intrinsic_call('__load_i64__', [self._int64_binary('__add__', pointer, self._int64_literal(loc, 8), loc)], 'int64', loc), self._optional_payload_address(target, loc)], ty.VOID_TYPE, loc),
                    hir.Assign(loc, ty.VOID_TYPE, offset_value, '+=', self._int64_literal(loc, 1)),
                ]
                exhausted_body = self._optional_write(
                    target,
                    hir.NoneValue(iterator.loc, 'none'),
                    payload,
                )
            elif payload is not None:
                defined_body = [
                    *value_updates,
                    *self._optional_write(target, value, payload),
                    hir.Assign(
                        iterator.loc,
                        ty.VOID_TYPE,
                        offset_value,
                        '+=',
                        self._int64_literal(iterator.loc, 1),
                    ),
                ]
                exhausted_body = self._optional_write(
                    target,
                    hir.NoneValue(iterator.loc, 'none'),
                    payload,
                )
            else:
                defined_body = [*value_updates]
                if not string_iterator:
                    defined_body.append(hir.Assign(
                        iterator.loc,
                        ty.VOID_TYPE,
                        replace(target, type=runtime_target_type),
                        '=',
                        value,
                    ))
                defined_body.append(
                    hir.Assign(
                        iterator.loc,
                        ty.VOID_TYPE,
                        offset_value,
                        '+=',
                        self._int64_literal(iterator.loc, 1),
                    )
                )
                exhausted_body = []
            updates.append(
                hir.Flow(
                    iterator.loc,
                    ty.VOID_TYPE,
                    [
                        hir.IfArm(
                            iterator.loc,
                            ty.VOID_TYPE,
                            replace(active, loc=iterator.loc),
                            hir.Block(
                                iterator.loc,
                                ty.VOID_TYPE,
                                defined_body,
                                True,
                            ),
                        )
                    ],
                    (
                        hir.Block(
                            iterator.loc,
                            ty.VOID_TYPE,
                            exhausted_body,
                            True,
                        )
                        if exhausted_body
                        else None
                    ),
                )
            )

        formula_stack: list[hir.AST] = []
        for token in condition.formula:
            if isinstance(token, int):
                formula_stack.append(active_values[token])
                continue
            right = formula_stack.pop()
            left = formula_stack.pop()
            formula_stack.append(
                self._bool_binary(token, left, right, node.loc)
            )
        formula = formula_stack[0]
        lowered_source = self._lower_loop_body(arm)
        source_items = (
            lowered_source.items
            if isinstance(lowered_source, hir.Block)
            else [lowered_source]
        )
        body_gate = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    node.loc,
                    ty.VOID_TYPE,
                    formula,
                    hir.Block(node.loc, ty.VOID_TYPE, source_items, True),
                )
            ],
            hir.Block(
                node.loc,
                ty.BOTTOM_TYPE,
                [hir.Break(node.loc, ty.BOTTOM_TYPE)],
                True,
            ),
        )
        loop_body = hir.Block(
            arm.body.loc,
            ty.VOID_TYPE,
            [*updates, body_gate],
            True,
        )
        loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    arm.loc,
                    ty.VOID_TYPE,
                    hir.Bool(node.loc, 'bool', True),
                    loop_body,
                )
            ],
            None,
        )
        return [*declarations, loop]

    def _require_finite_udewy_iterator(
        self,
        iterator: hir.IteratorExpression,
    ) -> None:
        if iterator.count is None:
            raise NotImplementedYet(Error(
                srcfile=self.srcfile,
                title='udewy unbounded range iteration requires bigint lowering',
                pointer_messages=[
                    Pointer(
                        span=iterator.iterable.loc,
                        message=(
                            'this iterator is semantically unbounded and cannot '
                            'use a wrapping int64 counter'
                        ),
                    )
                ],
            ))
        payload = ty.optional_payload(iterator.target.type)
        target_type = payload if payload is not None else iterator.target.type
        values = [
            iterator.first,
            iterator.step,
            iterator.count,
            *([iterator.last] if iterator.last is not None else []),
        ]
        supported_target = target_type == 'int64' or isinstance(
            target_type,
            ty.StringType,
        )
        if not supported_target or not all(
            ty.integer_literal_fits(value, 'int64')
            for value in values
        ):
            raise NotImplementedYet(Error(
                srcfile=self.srcfile,
                title='udewy range iteration requires bigint lowering',
                pointer_messages=[
                    Pointer(
                        span=iterator.iterable.loc,
                        message='this normalized iterator does not fit the int64 ABI',
                    )
                ],
            ))

    def _iterator_value(
        self,
        iterator: hir.IteratorExpression,
        offset: hir.AST,
    ) -> hir.AST:
        scaled_offset = (
            offset
            if iterator.step == 1
            else self._int64_binary(
                '__mul__',
                offset,
                self._int64_literal(iterator.loc, iterator.step),
                iterator.loc,
            )
        )
        return self._int64_binary(
            '__add__',
            self._int64_literal(iterator.loc, iterator.first),
            scaled_offset,
            iterator.loc,
        )

