"""Scalar control flow: conditions, typed operators, loop signals, shifts, and short-circuits.

Split from ``lower.py``; methods run as part of ``_Lowerer``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from ...parser import t0
from ...reporting import Span
from ...semantic import hir, ty
from ...semantic.hir_display import type_to_dewy
from .lowering_shared import (
    FIXED_INTEGER_WIDTHS,
    SIGNED_FIXED_INTS,
)


class _FlowLowering:
    def _extract_range_membership(
        self,
        node: hir.RangeMembership,
    ) -> tuple[list[hir.AST], hir.AST]:
        """Lower one eager range membership value into comparisons."""
        prelude, value = self._extract_expression(node.value)
        value_temp = self._new_range_temp(node.value, 'candidate')
        prelude.append(hir.Declare(
            node.value.loc,
            ty.VOID_TYPE,
            'let',
            value_temp.name,
            'int64',
            hir.ValueCast(node.value.loc, 'int64', value),
        ))

        conditions: list[hir.AST] = []
        if node.step is not None:
            if node.first is None or (
                node.count is None and node.last is not None
            ):
                raise TypeError('INTERNAL ERROR: incomplete stepped membership metadata')
            if node.count == 0:
                return prelude, hir.Bool(node.loc, 'bool', False)
            first = self._int64_literal(node.loc, node.first)
            if node.step > 0:
                conditions.append(self._int64_comparison(
                    '__ge__',
                    value_temp,
                    first,
                    node.loc,
                ))
                if node.last is not None:
                    conditions.append(self._int64_comparison(
                        '__le__',
                        value_temp,
                        self._int64_literal(node.loc, node.last),
                        node.loc,
                    ))
            else:
                conditions.append(self._int64_comparison(
                    '__le__',
                    value_temp,
                    first,
                    node.loc,
                ))
                if node.last is not None:
                    conditions.append(self._int64_comparison(
                        '__ge__',
                        value_temp,
                        self._int64_literal(node.loc, node.last),
                        node.loc,
                    ))
            if abs(node.step) != 1:
                divisor = self._int64_literal(node.loc, node.step)
                conditions.append(self._typed_equality(
                    self._int64_binary(
                        '__mod__',
                        value_temp,
                        divisor,
                        node.loc,
                    ),
                    self._int64_binary(
                        '__mod__',
                        first,
                        divisor,
                        node.loc,
                    ),
                    'int64',
                    node.loc,
                ))
        else:
            bounds = node.range.bounds or '[]'
            for role, anchor, comparison in (
                (
                    'lower',
                    node.range.left,
                    '__ge__' if bounds[0] == '[' else '__gt__',
                ),
                (
                    'upper',
                    node.range.right,
                    '__le__' if bounds[1] == ']' else '__lt__',
                ),
            ):
                if anchor is None:
                    continue
                anchor_prelude, lowered_anchor = self._extract_expression(anchor)
                prelude.extend(anchor_prelude)
                anchor_temp = self._new_range_temp(anchor, role)
                prelude.append(hir.Declare(
                    anchor.loc,
                    ty.VOID_TYPE,
                    'let',
                    anchor_temp.name,
                    'int64',
                    hir.ValueCast(anchor.loc, 'int64', lowered_anchor),
                ))
                conditions.append(self._int64_comparison(
                    comparison,
                    value_temp,
                    anchor_temp,
                    node.loc,
                ))

        if not conditions:
            return prelude, hir.Bool(node.loc, 'bool', True)
        condition = conditions[0]
        for next_condition in conditions[1:]:
            condition = hir.ShortCircuit(
                node.loc,
                'bool',
                'and',
                condition,
                next_condition,
            )
        condition_prelude, result = self._extract_expression(condition)
        return [*prelude, *condition_prelude], result

    @staticmethod
    def _bool_binary(
        op: hir.IteratorLogicalOp,
        left: hir.AST,
        right: hir.AST,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', 'bool'),
                ty.PosOrKwArg('right', 'bool'),
            ],
            [],
            None,
            'bool',
            [],
        )
        base_op: hir.IteratorLogicalOp = {
            'nand': 'and',
            'nor': 'or',
            'xnor': 'xor',
        }.get(op, op)
        call = hir.FunctionCall(
            loc,
            'bool',
            hir.ExpressedIdentifier(loc, function_type, f'__{base_op}__'),
            [left, right],
            {},
        )
        if op not in {'nand', 'nor', 'xnor'}:
            return call
        unary_type = ty.FunctionType(
            [ty.PosOrKwArg('item', 'bool')],
            [],
            None,
            'bool',
            [],
        )
        return hir.FunctionCall(
            loc,
            'bool',
            hir.ExpressedIdentifier(loc, unary_type, '__not__'),
            [call],
            {},
        )

    def _lower_flow(
        self,
        node: hir.Flow,
        *,
        target: hir.ExpressedIdentifier | None = None,
    ) -> tuple[list[hir.AST], hir.Flow]:
        """Lower one structured flow, optionally assigning each branch value."""
        prelude: list[hir.AST] = []
        arms: list[hir.IfArm | hir.LoopArm] = []
        for index, arm in enumerate(node.arms):
            # the condition's string temporaries (`loop f(x).length >? 0`, `else if
            # p(path).suffix =? ".dewy"`) are released where the condition runs: in a
            # loop's body after every test, in the nested `else` of a later arm, or
            # with the statement for a first arm
            outer_temporaries = self.statement_temporaries
            self.statement_temporaries = []
            try:
                condition_prelude, condition = self._prepare_condition(arm.condition)
            finally:
                condition_temporaries, self.statement_temporaries = self.statement_temporaries, outer_temporaries
            if (condition_prelude or condition_temporaries) and isinstance(arm, hir.LoopArm):
                # A loop condition that needs statements (`loop … and f(text[i])`):
                # they must run before every test, so the loop becomes
                # `loop true { statements; if not cond { break }; body }`
                # (`continue` returns to the top and re-tests, as it should).
                body = self._lower_loop_body(arm)
                loc = arm.condition.loc
                tested = hir.ExpressedIdentifier(loc, 'bool', self._new_string_temp(loc, 'bool', 'loop_test').name)
                declarations_and_releases = self._with_temporaries_released([], condition_temporaries)
                declarations = [item for item in declarations_and_releases if isinstance(item, hir.Declare)]
                releases = [item for item in declarations_and_releases if not isinstance(item, hir.Declare)]
                unary_type = ty.FunctionType([ty.PosOrKwArg('item', 'bool')], [], None, 'bool', [])
                negated = hir.FunctionCall(loc, 'bool', hir.ExpressedIdentifier(loc, unary_type, '__not__'), [tested], {})
                exit_test = hir.Flow(
                    loc, ty.VOID_TYPE,
                    [hir.IfArm(loc, ty.VOID_TYPE, negated, hir.Block(loc, ty.VOID_TYPE, [hir.Break(loc, ty.BOTTOM_TYPE)], True))],
                    None,
                )
                body_items = body.items if isinstance(body, hir.Block) else [body]
                arms.append(replace(
                    arm,
                    condition=hir.Bool(loc, 'bool', True),
                    body=hir.Block(arm.body.loc, ty.VOID_TYPE, [*declarations, *condition_prelude, hir.Declare(loc, ty.VOID_TYPE, 'let', tested.name, 'bool', condition), *releases, exit_test, *body_items], True),
                ))
                continue
            if condition_prelude or condition_temporaries:
                if index > 0:
                    # A later arm whose condition needs statements (a match
                    # arm reading a field of the narrowed scrutinee): the rest
                    # of the chain becomes a nested flow in the `else`, where
                    # those statements can run after the earlier tests failed
                    # (this attempt's temporaries are dropped: the nested
                    # lowering makes its own, released inside the `else`).
                    rest = replace(node, arms=list(node.arms[index:]))
                    outer_temporaries = self.statement_temporaries
                    self.statement_temporaries = []
                    try:
                        nested_prelude, nested = self._lower_flow(rest, target=target)
                    finally:
                        nested_temporaries, self.statement_temporaries = self.statement_temporaries, outer_temporaries
                    default = hir.Block(node.loc, ty.VOID_TYPE, self._with_temporaries_released([*nested_prelude, nested], nested_temporaries), True)
                    return prelude, replace(node, type=ty.VOID_TYPE if target is not None else node.type, arms=arms, default=default)
                prelude.extend(condition_prelude)
                self.statement_temporaries.extend(condition_temporaries)   # a first arm's: the statement's own
            if isinstance(arm, hir.LoopArm) and target is None:
                body = self._lower_loop_body(arm)
            else:
                if isinstance(arm, hir.LoopArm):
                    self.lower_loop_depth += 1
                body = (
                    self._assign_flow_body(arm.body, target)
                    if target is not None
                    else self._lower_statement_body(arm.body)
                )
                if isinstance(arm, hir.LoopArm):
                    self.lower_loop_depth -= 1
            arms.append(replace(arm, condition=condition, body=body))
        default = None
        if node.default is not None:
            default = (
                self._assign_flow_body(node.default, target)
                if target is not None
                else self._lower_statement_body(node.default)
            )
        return prelude, replace(node, type=ty.VOID_TYPE if target is not None else node.type, arms=arms, default=default)

    @staticmethod
    def _int64_comparison(
        name: Literal['__lt__', '__le__', '__gt__', '__ge__'],
        left: hir.AST,
        right: hir.AST,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', 'int64'),
                ty.PosOrKwArg('right', 'int64'),
            ],
            [],
            None,
            'bool',
            [],
        )
        return hir.FunctionCall(
            loc,
            'bool',
            hir.ExpressedIdentifier(loc, function_type, name),
            [left, right],
            {},
        )

    @staticmethod
    def _typed_equality(
        left: hir.AST,
        right: hir.AST,
        operand_type: ty.TypeExpr,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', operand_type),
                ty.PosOrKwArg('right', operand_type),
            ],
            [],
            None,
            'bool',
            [],
        )
        return hir.FunctionCall(
            loc,
            'bool',
            hir.ExpressedIdentifier(loc, function_type, '__eq__'),
            [left, right],
            {},
        )

    def _prepare_condition(self, node: hir.AST) -> tuple[list[hir.AST], hir.AST]:
        """Preserve lazy boolean operators while lowering their operands."""
        if isinstance(node, hir.ShortCircuit):
            left_prelude, left = self._prepare_condition(node.left)
            right_prelude, right = self._prepare_condition(node.right)
            if right_prelude:
                target = self._new_eager_temp(node)
                declaration = hir.Declare(
                    node.loc,
                    ty.VOID_TYPE,
                    'let',
                    target.name,
                    'bool',
                    hir.Bool(node.loc, 'bool', False),
                )
                false = hir.Bool(node.loc, 'bool', False)
                negated_right = self._typed_equality(
                    right,
                    false,
                    'bool',
                    node.loc,
                )
                if node.op in {'and', 'nand'}:
                    true_value = right if node.op == 'and' else negated_right
                    false_value: hir.AST = (
                        false
                        if node.op == 'and'
                        else hir.Bool(node.loc, 'bool', True)
                    )
                    true_body = hir.Block(
                        node.loc,
                        ty.VOID_TYPE,
                        [
                            *right_prelude,
                            hir.Assign(
                                node.loc,
                                ty.VOID_TYPE,
                                target,
                                '=',
                                true_value,
                            ),
                        ],
                        True,
                    )
                    default = hir.Assign(
                        node.loc,
                        ty.VOID_TYPE,
                        target,
                        '=',
                        false_value,
                    )
                else:
                    true_value = (
                        hir.Bool(node.loc, 'bool', True)
                        if node.op == 'or'
                        else false
                    )
                    right_value = right if node.op == 'or' else negated_right
                    true_body = hir.Assign(
                        node.loc,
                        ty.VOID_TYPE,
                        target,
                        '=',
                        true_value,
                    )
                    default = hir.Block(
                        node.loc,
                        ty.VOID_TYPE,
                        [
                            *right_prelude,
                            hir.Assign(
                                node.loc,
                                ty.VOID_TYPE,
                                target,
                                '=',
                                right_value,
                            ),
                        ],
                        True,
                    )
                flow = hir.Flow(
                    node.loc,
                    ty.VOID_TYPE,
                    [
                        hir.IfArm(
                            node.loc,
                            ty.VOID_TYPE,
                            left,
                            true_body,
                        )
                    ],
                    default,
                )
                return [*left_prelude, declaration, flow], target
            return left_prelude, replace(node, left=left, right=right)
        return self._extract_expression(node)

    def _assign_flow_body(
        self,
        body: hir.AST,
        target: hir.ExpressedIdentifier,
    ) -> hir.AST:
        """Replace a continuing scalar branch result with a temporary assignment."""
        if body.type == ty.BOTTOM_TYPE:
            return self._lower_statement_body(body)
        if isinstance(body, hir.Block) and body.scoped:
            value_indices = [
                index
                for index, item in enumerate(body.items)
                if item.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
            ]
            if len(value_indices) != 1:
                self._target_error(body, 'conditional branch does not have one scalar value')
            value_index = value_indices[0]
            items: list[hir.AST] = []
            for index, item in enumerate(body.items):
                if index != value_index:
                    items.extend(self._lower_statement(item))
                    continue
                prelude, value = self._enum_aware_extract(item, target)
                items.extend(prelude)
                items.append(self._flow_assignment(target, value))
            return replace(body, type=ty.VOID_TYPE, items=items)
        prelude, value = self._enum_aware_extract(body, target)
        statements = [*prelude, self._flow_assignment(target, value)]
        return hir.Block(body.loc, ty.VOID_TYPE, statements, True)

    @staticmethod
    def _flow_assignment(
        target: hir.ExpressedIdentifier,
        value: hir.AST,
    ) -> hir.Assign:
        """Build a synthetic assignment to a flow-result temporary."""
        use = replace(target, loc=value.loc)
        return hir.Assign(value.loc, ty.VOID_TYPE, use, '=', value)

    def _new_flow_temp(self, node: hir.AST) -> hir.ExpressedIdentifier:
        """Allocate a deterministic temporary absent from all source bindings."""
        while True:
            name = f'__dewy_flow_{self.next_flow_temp}'
            self.next_flow_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                temp_type = node.type
                if isinstance(temp_type, ty.IntegerLiteralType) or temp_type in ('int', 'uint'):
                    temp_type = 'int64'  # abstract and literal integers are words by now
                elif isinstance(temp_type, ty.TypeOr) and (ty.string_valued(temp_type) or self._is_optional_element(temp_type) or self._is_union_element(temp_type)):
                    temp_type = 'int64'  # one-word handles
                return hir.ExpressedIdentifier(node.loc, temp_type, name)

    def _is_fixed_width_shift(self, node: hir.FunctionCall) -> bool:
        """Whether ``node`` needs an explicit source-width shift guard."""
        if (
            self.preserve_raw_udewy_shifts
            or not isinstance(node.func, hir.ExpressedIdentifier)
            or node.func.name not in {'__lshift__', '__rshift__'}
            or len(node.pos_args) != 2
            or node.kw_args
            or not isinstance(node.func.type, ty.FunctionType)
            or not node.func.type.pos_or_kw
        ):
            return False
        return node.func.type.pos_or_kw[0].type in FIXED_INTEGER_WIDTHS

    def _extract_fixed_width_shift(
        self,
        node: hir.FunctionCall,
    ) -> tuple[list[hir.AST], hir.AST]:
        """Lower a fixed-width shift with one-time operands and a width guard.

        udewy's machine-word shifts mask their count modulo 64. Dewy instead
        accepts only unsigned counts and continues the source shift beyond its
        width, including sign extension for signed right shifts, so this guard
        must be represented before source emission.
        """
        assert isinstance(node.func, hir.ExpressedIdentifier)
        assert isinstance(node.func.type, ty.FunctionType)
        operand_type = node.func.type.pos_or_kw[0].type
        assert isinstance(operand_type, str)
        width = FIXED_INTEGER_WIDTHS[operand_type]
        if not (isinstance(node.type, str) and node.type in FIXED_INTEGER_WIDTHS):
            # a literal left operand (`1 << n`) was promoted to the operand
            # width; the result and its temporaries take that width too
            node = replace(node, type=operand_type)

        left_prelude, left = self._extract_expression(node.pos_args[0])
        left_temp = self._new_shift_temp(left, operand_type, 'value')
        left_declaration = hir.Declare(
            left.loc,
            ty.VOID_TYPE,
            'let',
            left_temp.name,
            operand_type,
            left,
        )

        count_prelude, count = self._extract_expression(node.pos_args[1])
        count_temp = self._new_shift_temp(count, 'uint64', 'count')
        count_declaration = hir.Declare(
            count.loc,
            ty.VOID_TYPE,
            'let',
            count_temp.name,
            'uint64',
            hir.ValueCast(count.loc, 'uint64', count),
        )

        width_count = hir.Integer(node.loc, 'uint64', t0.base10, width)
        count_reaches_width = self._intrinsic_call(
            '__unsigned_gte__',
            [count_temp, width_count],
            'bool',
            node.loc,
        )

        zero_result = hir.Integer(node.loc, node.type, t0.base10, 0)
        overshift_result: hir.AST = zero_result
        if node.func.name == '__rshift__' and operand_type in SIGNED_FIXED_INTS:
            overshift_result = hir.ValueCast(
                node.loc,
                node.type,
                self._intrinsic_call(
                    '__signed_shr__',
                    [
                        replace(left_temp, type='int64'),
                        self._int64_literal(node.loc, 63),
                    ],
                    'int64',
                    node.loc,
                ),
            )

        wide_type = 'int64' if operand_type in SIGNED_FIXED_INTS else 'uint64'
        wide_left = replace(left_temp, type=wide_type)
        if node.func.name == '__rshift__' and wide_type == 'int64':
            safe_shift: hir.AST = self._intrinsic_call(
                '__signed_shr__',
                [wide_left, count_temp],
                'int64',
                node.loc,
            )
        else:
            raw_shift = (
                '__dewy_raw_lshift__'
                if node.func.name == '__lshift__'
                else '__dewy_raw_rshift__'
            )
            safe_shift = self._typed_binary(
                raw_shift,
                wide_left,
                count_temp,
                wide_type,
                'uint64',
                wide_type,
                node.loc,
            )

        if node.func.name == '__lshift__' and width < 64:
            if wide_type == 'uint64':
                mask = hir.Integer(
                    node.loc,
                    'uint64',
                    t0.base10,
                    (1 << width) - 1,
                )
                safe_shift = self._typed_binary(
                    '__and__',
                    safe_shift,
                    mask,
                    'uint64',
                    'uint64',
                    'uint64',
                    node.loc,
                )
            else:
                sign_shift = self._int64_literal(node.loc, 64 - width)
                safe_shift = self._intrinsic_call(
                    '__signed_shr__',
                    [
                        self._typed_binary(
                            '__dewy_raw_lshift__',
                            safe_shift,
                            sign_shift,
                            'int64',
                            'int64',
                            'int64',
                            node.loc,
                        ),
                        sign_shift,
                    ],
                    'int64',
                    node.loc,
                )

        guarded = hir.Flow(
            node.loc,
            node.type,
            [
                hir.IfArm(
                    node.loc,
                    node.type,
                    count_reaches_width,
                    overshift_result,
                ),
            ],
            hir.ValueCast(node.loc, node.type, safe_shift),
        )
        shift_prelude, result = self._extract_expression(guarded)
        return [
            *left_prelude,
            left_declaration,
            *count_prelude,
            count_declaration,
            *shift_prelude,
        ], result

    @staticmethod
    def _typed_binary(
        name: str,
        left: hir.AST,
        right: hir.AST,
        left_type: ty.TypeExpr,
        right_type: ty.TypeExpr,
        result_type: ty.Type,
        loc: Span,
    ) -> hir.FunctionCall:
        """Build an already-selected binary call with explicit operand types."""
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', left_type),
                ty.PosOrKwArg('right', right_type),
            ],
            [],
            None,
            result_type,
        )
        return hir.FunctionCall(
            loc,
            result_type,
            hir.ExpressedIdentifier(loc, function_type, name),
            [left, right],
            {},
        )

    def _new_eager_temp(self, node: hir.AST) -> hir.ExpressedIdentifier:
        """Allocate an argument temporary that forces eager logical-call evaluation."""
        while True:
            name = f'__dewy_eager_{self.next_eager_temp}'
            self.next_eager_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(node.loc, 'bool', name)

    def _new_shift_temp(
        self,
        node: hir.AST,
        type_: ty.Type,
        role: str,
    ) -> hir.ExpressedIdentifier:
        """Allocate an operand temporary for a width-checked shift."""
        while True:
            name = f'__dewy_shift_{role}_{self.next_shift_temp}'
            self.next_shift_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(node.loc, type_, name)

    def _new_range_temp(
        self,
        node: hir.AST,
        role: str,
    ) -> hir.ExpressedIdentifier:
        """Allocate a runtime range-membership operand temporary."""
        while True:
            name = f'__dewy_range_{role}_{self.next_range_temp}'
            self.next_range_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(node.loc, 'int64', name)

    def _new_loop_signals(
        self,
        node: hir.AST,
    ) -> tuple[hir.ExpressedIdentifier, hir.ExpressedIdentifier]:
        """Allocate collision-free outward-level and exit-kind signal names."""
        while True:
            ordinal = self.next_loop_signal
            self.next_loop_signal += 1
            levels_name = f'__dewy_loop_levels_{ordinal}'
            kind_name = f'__dewy_loop_kind_{ordinal}'
            if levels_name in self.source_names or kind_name in self.source_names:
                continue
            self.source_names.update({levels_name, kind_name})
            return (
                hir.ExpressedIdentifier(node.loc, 'int64', levels_name),
                hir.ExpressedIdentifier(node.loc, 'int64', kind_name),
            )

    def _loop_signal_declarations(self, loc: Span) -> list[hir.Declare]:
        """Initialize the current function's labeled-exit signals."""
        assert self.loop_signal_levels is not None
        assert self.loop_signal_kind is not None
        zero = self._int64_literal(loc, 0)
        return [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                self.loop_signal_levels.name,
                'int64',
                zero,
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                self.loop_signal_kind.name,
                'int64',
                replace(zero),
            ),
        ]

    @classmethod
    def _loop_signal_assignment(
        cls,
        target: hir.ExpressedIdentifier,
        value: int,
        loc: Span,
    ) -> hir.Assign:
        return hir.Assign(
            loc,
            ty.VOID_TYPE,
            replace(target, loc=loc),
            '=',
            cls._int64_literal(loc, value),
        )

    @classmethod
    def _loop_signal_condition(
        cls,
        target: hir.ExpressedIdentifier,
        dunder: Literal['__eq__', '__gt__'],
        value: int,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', 'int64'),
                ty.PosOrKwArg('right', 'int64'),
            ],
            [],
            None,
            'bool',
            [],
        )
        function = hir.ExpressedIdentifier(loc, function_type, dunder)
        return hir.FunctionCall(
            loc,
            'bool',
            function,
            [
                replace(target, loc=loc),
                cls._int64_literal(loc, value),
            ],
            {},
        )

    def _loop_signal_checkpoint(self, loc: Span) -> list[hir.Flow]:
        """Handle or propagate a pending nonlocal exit after one nested loop."""
        assert self.loop_signal_levels is not None
        assert self.loop_signal_kind is not None

        break_body = hir.Block(
            loc,
            ty.BOTTOM_TYPE,
            [
                self._loop_signal_assignment(self.loop_signal_kind, 0, loc),
                hir.Break(loc, ty.BOTTOM_TYPE),
            ],
            True,
        )
        continue_body = hir.Block(
            loc,
            ty.BOTTOM_TYPE,
            [
                self._loop_signal_assignment(self.loop_signal_kind, 0, loc),
                hir.Continue(loc, ty.BOTTOM_TYPE),
            ],
            True,
        )
        kind_flow = hir.Flow(
            loc,
            ty.BOTTOM_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.BOTTOM_TYPE,
                    self._loop_signal_condition(
                        self.loop_signal_kind,
                        '__eq__',
                        1,
                        loc,
                    ),
                    break_body,
                ),
            ],
            continue_body,
        )
        target_body = hir.Block(
            loc,
            ty.BOTTOM_TYPE,
            [
                self._loop_signal_assignment(self.loop_signal_levels, 0, loc),
                kind_flow,
            ],
            True,
        )
        target_checkpoint = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.BOTTOM_TYPE,
                    self._loop_signal_condition(
                        self.loop_signal_levels,
                        '__eq__',
                        1,
                        loc,
                    ),
                    target_body,
                ),
            ],
            None,
        )

        propagate_body = hir.Block(
            loc,
            ty.BOTTOM_TYPE,
            [
                hir.Assign(
                    loc,
                    ty.VOID_TYPE,
                    replace(self.loop_signal_levels, loc=loc),
                    '-=',
                    self._int64_literal(loc, 1),
                ),
                hir.Break(loc, ty.BOTTOM_TYPE),
            ],
            True,
        )
        propagate_checkpoint = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.BOTTOM_TYPE,
                    self._loop_signal_condition(
                        self.loop_signal_levels,
                        '__gt__',
                        1,
                        loc,
                    ),
                    propagate_body,
                ),
            ],
            None,
        )
        return [target_checkpoint, propagate_checkpoint]

    @staticmethod
    def _is_eager_bool_logical_call(node: hir.FunctionCall) -> bool:
        """Whether target operator syntax needs pre-evaluated direct-call operands."""
        return (
            isinstance(node.func, hir.ExpressedIdentifier)
            and node.func.name in {'__and__', '__or__', '__nand__', '__nor__'}
            and isinstance(node.func.type, ty.FunctionType)
            and all(param.type == 'bool' for param in node.func.type.pos_or_kw)
        )

    def _enum_aware_extract(self, item: hir.AST, target: hir.ExpressedIdentifier) -> tuple[list[hir.AST], hir.AST]:
        """A flow branch value for its temporary: an enum-typed temporary takes the member's tag word."""
        members = ty.enum_members(target.type)
        if members is not None:
            return self._enum_word_of(item, members)
        if self._is_string_valued(item.type):
            return self._kept_string_value(item)   # the flow's temporary keeps a call's result
        return self._extract_expression(item)

    def _placeholder(self, node: hir.AST) -> hir.AST:
        """Return an udewy-representable initializer for a flow temporary."""
        if isinstance(node.type, ty.RefinedType):
            node = replace(node, type=node.type.base)   # `int64<0..100>` is an int64 word
        if ty.enum_members(node.type) is not None:
            return hir.Integer(node.loc, 'int64', t0.base10, 0)   # an enum is its tag word
        if node.type == 'bool':
            return hir.Bool(node.loc, 'bool', False)
        if isinstance(node.type, str) and node.type in {
            'int8',
            'int16',
            'int32',
            'int64',
            'uint8',
            'uint16',
            'uint32',
            'uint64',
        }:
            return hir.Integer(node.loc, node.type, t0.base10, 0)
        if isinstance(node.type, ty.IntegerLiteralType) or node.type in ('int', 'uint'):
            # abstract and literal-typed integers are 64-bit words by lowering time
            return hir.Integer(node.loc, 'int64', t0.base10, 0)
        if isinstance(node.type, ty.QuantityType):
            runtime_type = self._lower_runtime_value_type(node.type)
            if isinstance(runtime_type, str):
                return hir.Integer(node.loc, runtime_type, t0.base10, 0)
        if isinstance(
            node.type,
            (
                ty.ArrayType,
                ty.StringLiteralType,
                ty.BinaryLiteralType,
                ty.StringType,
            ),
        ) or (
            isinstance(node.type, str)
            and node.type in {'string', 'grapheme', 'char'}
        ) or ty.string_valued(node.type) or self._is_optional_element(node.type):
            # one-word handles: string-literal unions and optional cells
            return hir.Integer(node.loc, 'int64', t0.base10, 0)
        self._target_error(
            node,
            f'no udewy flow temporary representation for `{type_to_dewy(node.type)}`',
        )

    def _short_circuit_flow(self, node: hir.ShortCircuit) -> hir.Flow:
        """Expand a value-position lazy boolean operator into an equivalent flow."""
        true = hir.Bool(node.loc, 'bool', True)
        false = hir.Bool(node.loc, 'bool', False)
        if node.op == 'and':
            consequent, default = node.right, false
        elif node.op == 'or':
            consequent, default = true, node.right
        elif node.op == 'nand':
            consequent, default = self._bool_not(node.right), true
        else:
            assert node.op == 'nor'
            consequent, default = false, self._bool_not(node.right)
        arm = hir.IfArm(node.loc, 'bool', node.left, consequent)
        return hir.Flow(node.loc, 'bool', [arm], default)

    @staticmethod
    def _bool_not(node: hir.AST) -> hir.FunctionCall:
        """Build the concrete boolean negation used by `nand` and `nor`."""
        function_type = ty.FunctionType(
            [ty.PosOrKwArg('item', 'bool')],
            [],
            None,
            'bool',
            [],
        )
        function = hir.ExpressedIdentifier(node.loc, function_type, '__not__')
        return hir.FunctionCall(node.loc, 'bool', function, [node], {})

