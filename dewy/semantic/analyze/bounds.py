"""Flow-sensitive integer bounds validation for checked HIR."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ...reporting import Pointer, SrcFile
from .. import bindings as sb
from .. import hir, ty
from ..errors import user_error


@dataclass(frozen=True)
class Interval:
    """An inclusive integer interval; ``None`` denotes an infinite endpoint."""

    lower: int | None
    upper: int | None

    @classmethod
    def exact(cls, value: int) -> Interval:
        return cls(value, value)

    @property
    def is_empty(self) -> bool:
        return (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        )

    def intersect(self, other: Interval) -> Interval:
        lower = _maximum_lower(self.lower, other.lower)
        upper = _minimum_upper(self.upper, other.upper)
        return Interval(lower, upper)

    def union(self, other: Interval) -> Interval:
        lower = (
            None
            if self.lower is None or other.lower is None
            else min(self.lower, other.lower)
        )
        upper = (
            None
            if self.upper is None or other.upper is None
            else max(self.upper, other.upper)
        )
        return Interval(lower, upper)

    def widen(self, other: Interval) -> Interval:
        lower = (
            self.lower
            if self.lower is not None
            and other.lower is not None
            and other.lower >= self.lower
            else None
        )
        upper = (
            self.upper
            if self.upper is not None
            and other.upper is not None
            and other.upper <= self.upper
            else None
        )
        return Interval(lower, upper)


UNKNOWN_INTERVAL = Interval(None, None)
EMPTY_INTERVAL = Interval(1, 0)
State = dict[int, Interval]

# Runtime-length arrays contribute two kinds of synthetic state entries, keyed
# by negative ids so they never collide with bindings: the array's *length
# interval* (refined by `xs.length >? k` and stepped by growth methods) and
# *index facts* recording that an index binding is proven below an array's
# length (from `i <? xs.length`). Joins and widening only keep keys common to
# both sides, which is exactly the sound treatment for facts.
_FACT_BASE = 1 << 40
_FACT_SHIFT = 20

# A runtime-length array's length is a nonnegative int64, which keeps
# `i <? xs.length` bounded above so `i + 1` cannot roll over.
_MAX_LENGTH = (1 << 63) - 1


def _length_key(array_id: int) -> int:
    return -array_id - 1


def _index_fact_key(index_id: int, array_id: int) -> int:
    return -(_FACT_BASE + (index_id << _FACT_SHIFT) + array_id)


def _decode_index_fact(key: int) -> tuple[int, int] | None:
    if key > -_FACT_BASE:
        return None
    raw = -key - _FACT_BASE
    return raw >> _FACT_SHIFT, raw & ((1 << _FACT_SHIFT) - 1)


def _runtime_array_id(node: hir.AST) -> int | None:
    """The binding id of a named runtime-length array, else None."""
    while isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
        node = node.expr
    if (
        isinstance(node, hir.ExpressedIdentifier)
        and node.binding_id is not None
        and isinstance(node.type, ty.ArrayType)
        and node.type.length is None
    ):
        return node.binding_id
    return None


def _drop_index_facts(
    state: State,
    *,
    index_id: int | None = None,
    array_id: int | None = None,
) -> None:
    for key in [key for key in state if key <= -_FACT_BASE]:
        decoded = _decode_index_fact(key)
        if decoded is None:
            continue
        fact_index, fact_array = decoded
        if (index_id is not None and fact_index == index_id) or (
            array_id is not None and fact_array == array_id
        ):
            del state[key]


@dataclass
class _LoopTransfer:
    normal: State | None
    breaks: dict[int, list[State]]
    continues: dict[int, list[State]]


def _maximum_lower(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _minimum_upper(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _add(left: int | None, right: int | None) -> int | None:
    return None if left is None or right is None else left + right


def _subtract(left: int | None, right: int | None) -> int | None:
    return None if left is None or right is None else left - right


_WORD_ARITHMETIC = {'__add__', '__sub__', '__mul__', '__floordiv__', '__mod__', '__lshift__', '__rshift__'}


def _assigned_binding_ids(root: hir.AST) -> set[int]:
    """Binding ids that some assignment or mutable place targets anywhere."""
    found: set[int] = set()

    def root_binding(node: hir.AST) -> int | None:
        while isinstance(node, (hir.MemberAccess, hir.Index)):
            node = node.value if isinstance(node, hir.MemberAccess) else node.array
        return node.binding_id if isinstance(node, hir.ExpressedIdentifier) else None

    def walk(value: object) -> None:
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
            return
        if not isinstance(value, hir.AST):
            return
        if isinstance(value, hir.Assign):
            binding_id = root_binding(value.target)
            if binding_id is not None:
                found.add(binding_id)
        elif isinstance(value, (hir.IndexAssign, hir.Place)):
            binding_id = root_binding(value.target)
            if binding_id is not None:
                found.add(binding_id)
        elif isinstance(value, hir.FunctionCall) and isinstance(value.func, hir.ArrayMethod):
            binding_id = root_binding(value.func.array)
            if binding_id is not None:
                found.add(binding_id)
        for field_name in getattr(value, '__dataclass_fields__', {}):
            walk(getattr(value, field_name))

    walk(root)
    return found


def _truncate_divide(numerator: int, divisor: int) -> int:
    quotient = abs(numerator) // abs(divisor)
    return -quotient if (numerator < 0) != (divisor < 0) else quotient


def _multiply(interval: Interval, other: Interval) -> Interval:
    if (
        interval.lower is None
        or interval.upper is None
        or other.lower is None
        or other.upper is None
    ):
        return UNKNOWN_INTERVAL
    products = [
        interval.lower * other.lower,
        interval.lower * other.upper,
        interval.upper * other.lower,
        interval.upper * other.upper,
    ]
    return Interval(min(products), max(products))


class _BoundsValidator:
    def __init__(
        self,
        registry: sb.BindingRegistry,
        srcfile: SrcFile,
        root: hir.Block,
    ) -> None:
        self.registry = registry
        self.srcfile = srcfile
        self.checked_functions: set[int] = set()
        assigned = _assigned_binding_ids(root)
        # Module-level `let` bindings that are never reassigned keep their
        # proven intervals inside function bodies; assigned ones are unknown
        # there because any call may change them.
        self.mutable_globals = {
            item.binding_id
            for item in root.items
            if isinstance(item, hir.Declare)
            and item.decltype == 'let'
            and item.binding_id is not None
            and item.binding_id in assigned
        }

    def validate(self, root: hir.Block) -> None:
        self._analyze(root, {}, validate=True)

    def _analyze(
        self,
        node: hir.AST,
        state: State,
        *,
        validate: bool,
    ) -> State:
        current = dict(state)
        if isinstance(node, hir.Block):
            local_ids = {
                item.binding_id
                for item in node.items
                if isinstance(item, hir.Declare) and item.binding_id is not None
            }
            for item in node.items:
                current = self._analyze(item, current, validate=validate)
            if node.scoped:
                for binding_id in local_ids:
                    current.pop(binding_id, None)
            return current
        if isinstance(node, hir.Declare):
            interval = self._eval(node.expr, current, validate=validate)
            if isinstance(node.annotation, ty.RefinedType) and node.binding_id is not None:
                interval = self._seed_refinements(node, current, interval)
            if isinstance(node.expr, hir.FunctionLiteral):
                self._analyze_function(node.expr, validate=validate, enclosing=current)
            elif isinstance(node.expr, hir.OverloadedFunction):
                for alternate in node.expr.alternates:
                    if isinstance(alternate, hir.FunctionLiteral):
                        self._analyze_function(alternate, validate=validate, enclosing=current)
            if node.binding_id is not None:
                self._set_interval(current, node.binding_id, interval)
            return current
        if isinstance(node, hir.Assign):
            value = self._eval(node.value, current, validate=validate)
            binding_id = node.target.binding_id
            if binding_id is None:
                return current
            if node.op == '+=':
                value = self._binary_interval(
                    '__add__',
                    current.get(binding_id),
                    value,
                    node.target.type,
                )
            elif node.op == '-=':
                value = self._binary_interval(
                    '__sub__',
                    current.get(binding_id),
                    value,
                    node.target.type,
                )
            elif node.op != '=':
                value = None
            self._set_interval(current, binding_id, value)
            _drop_index_facts(current, index_id=binding_id)
            if isinstance(node.target.type, ty.ArrayType) and node.target.type.length is None:
                # Whole-array replacement: nothing is known about the new length.
                current.pop(_length_key(binding_id), None)
                _drop_index_facts(current, array_id=binding_id)
            return current
        if isinstance(node, hir.IndexAssign):
            self._eval(node.target, current, validate=validate)
            self._eval(node.value, current, validate=validate)
            return current
        if isinstance(node, hir.Flow):
            return self._analyze_flow(node, current, validate=validate)
        if isinstance(node, hir.Return):
            if node.item is not None:
                self._eval(node.item, current, validate=validate)
            return current
        self._eval(node, current, validate=validate)
        return current

    def _analyze_function(
        self,
        function: hir.FunctionLiteral,
        *,
        validate: bool,
        enclosing: State | None = None,
    ) -> None:
        function_id = id(function)
        if function_id in self.checked_functions:
            return
        self.checked_functions.add(function_id)
        state: State = {
            key: interval
            for key, interval in (enclosing or {}).items()
            if key not in self.mutable_globals
        }
        for param in [
            *function.pos_or_kw_args,
            *function.kw_only_args,
            *([function.rest_args] if function.rest_args is not None else []),
        ]:
            if isinstance(param, hir.BoundParam):
                self._eval(param.value, state, validate=validate)
        self._analyze(function.body, state, validate=validate)

    def _analyze_flow(
        self,
        node: hir.Flow,
        state: State,
        *,
        validate: bool,
    ) -> State:
        if len(node.arms) == 1 and isinstance(node.arms[0], hir.LoopArm):
            arm = node.arms[0]
            if isinstance(arm.condition, hir.IteratorExpression):
                return self._analyze_iterator_loop(
                    arm.condition,
                    arm.body,
                    state,
                    validate=validate,
                )
            if isinstance(arm.condition, hir.MultiIteratorExpression):
                return self._analyze_multi_iterator_loop(
                    arm.condition,
                    arm.body,
                    state,
                    validate=validate,
                )
            return self._analyze_while_loop(
                arm.condition,
                arm.body,
                state,
                validate=validate,
            )

        remaining: State | None = dict(state)
        exits: list[State] = []
        for arm in node.arms:
            if remaining is None:
                break
            self._eval(arm.condition, remaining, validate=validate)
            true_state = self._refine(remaining, arm.condition, truth=True)
            if true_state is not None:
                exits.append(self._analyze(arm.body, true_state, validate=validate))
            false_state = self._refine(remaining, arm.condition, truth=False)
            if false_state is None:
                remaining = None
                break
            remaining = false_state
        if node.default is not None and remaining is not None:
            exits.append(self._analyze(node.default, remaining, validate=validate))
        elif node.default is None and remaining is not None:
            exits.append(remaining)
        return dict(state) if not exits else self._join_states(exits)

    def _analyze_while_loop(
        self,
        condition: hir.AST,
        body: hir.AST,
        state: State,
        *,
        validate: bool,
    ) -> State:
        head = dict(state)
        for _ in range(8):
            true_state = self._refine(head, condition, truth=True)
            if true_state is None:
                break
            transfer = self._loop_transfer(body, true_state, validate=False)
            backedges = [
                *([transfer.normal] if transfer.normal is not None else []),
                *transfer.continues.get(0, []),
            ]
            candidate = self._join_states([state, *backedges])
            widened = self._widen_states(head, candidate)
            if widened == head:
                break
            head = widened

        self._eval(condition, head, validate=validate)
        true_state = self._refine(head, condition, truth=True)
        break_exits: list[State] = []
        if true_state is not None:
            transfer = self._loop_transfer(body, true_state, validate=validate)
            break_exits.extend(transfer.breaks.get(0, []))
        false_state = self._refine(head, condition, truth=False)
        exits = [*break_exits]
        if false_state is not None:
            exits.append(false_state)
        return dict(state) if not exits else self._join_states(exits)

    def _analyze_iterator_loop(
        self,
        iterator: hir.IteratorExpression,
        body: hir.AST,
        state: State,
        *,
        validate: bool,
    ) -> State:
        self._eval(iterator.iterable, state, validate=validate)
        if iterator.count == 0:
            return dict(state)
        target_ids = {iterator.target.binding_id} - {None}

        def enter(head: State) -> State:
            body_state = dict(head)
            if iterator.target.binding_id is not None:
                body_state[iterator.target.binding_id] = self._iterator_interval(iterator)
            return body_state

        return self._iterate_loop(body, state, enter, target_ids, validate=validate)

    def _iterate_loop(
        self,
        body: hir.AST,
        state: State,
        enter: 'Callable[[State], State]',
        target_ids: set[int],
        *,
        validate: bool,
    ) -> State:
        """Widen loop-carried state to a fixed point, then validate the body once.

        Without this, an accumulator such as `total = total + step` would be
        analyzed from the entry state only and its growth across iterations
        would be invisible.
        """
        head = dict(state)
        for _ in range(8):
            transfer = self._loop_transfer(body, enter(head), validate=False)
            backedges = [
                *([transfer.normal] if transfer.normal is not None else []),
                *transfer.continues.get(0, []),
            ]
            for backedge in backedges:
                for binding_id in target_ids:
                    backedge.pop(binding_id, None)
            candidate = self._join_states([state, *backedges])
            widened = self._widen_states(head, candidate)
            if widened == head:
                break
            head = widened
        transfer = self._loop_transfer(body, enter(head), validate=validate)
        exits = [
            *([transfer.normal] if transfer.normal is not None else []),
            *transfer.breaks.get(0, []),
        ]
        for exit_state in exits:
            for binding_id in target_ids:
                exit_state.pop(binding_id, None)
        return self._join_states([state, *exits])

    def _analyze_multi_iterator_loop(
        self,
        condition: hir.MultiIteratorExpression,
        body: hir.AST,
        state: State,
        *,
        validate: bool,
    ) -> State:
        for iterator in condition.iterators:
            self._eval(iterator.iterable, state, validate=validate)
        target_ids = {
            iterator.target.binding_id
            for iterator in condition.iterators
            if iterator.target.binding_id is not None
        }

        def enter(head: State) -> State:
            body_state = dict(head)
            for iterator in condition.iterators:
                if iterator.count != 0 and iterator.target.binding_id is not None:
                    body_state[iterator.target.binding_id] = self._iterator_interval(iterator)
            return body_state

        return self._iterate_loop(body, state, enter, target_ids, validate=validate)

    @staticmethod
    def _iterator_interval(iterator: hir.IteratorExpression) -> Interval:
        if isinstance(iterator.iterable.type, ty.ArrayType):
            target_type = ty.optional_payload(iterator.target.type)
            if target_type is None:
                target_type = iterator.target.type
            layout = ty.fixed_integer_layout(target_type)
            if layout is None:
                return UNKNOWN_INTERVAL
            width, signed = layout
            return (
                Interval(-(1 << (width - 1)), (1 << (width - 1)) - 1)
                if signed
                else Interval(0, (1 << width) - 1)
            )
        if iterator.count is None:
            return (
                Interval(iterator.first, None)
                if iterator.step > 0
                else Interval(None, iterator.first)
            )
        if iterator.last is None:
            raise ValueError('INTERNAL ERROR: finite iterator has no last value')
        return Interval(
            min(iterator.first, iterator.last),
            max(iterator.first, iterator.last),
        )

    def _loop_transfer(
        self,
        node: hir.AST,
        state: State,
        *,
        validate: bool,
    ) -> _LoopTransfer:
        if isinstance(node, hir.Block):
            current: State | None = dict(state)
            breaks: dict[int, list[State]] = {}
            continues: dict[int, list[State]] = {}
            local_ids = {
                item.binding_id
                for item in node.items
                if isinstance(item, hir.Declare) and item.binding_id is not None
            }
            for item in node.items:
                if current is None:
                    break
                transfer = self._loop_transfer(item, current, validate=validate)
                current = transfer.normal
                self._merge_exit_maps(breaks, transfer.breaks)
                self._merge_exit_maps(continues, transfer.continues)
            if node.scoped:
                for exit_state in [
                    *([current] if current is not None else []),
                    *(state for states in breaks.values() for state in states),
                    *(state for states in continues.values() for state in states),
                ]:
                    for binding_id in local_ids:
                        exit_state.pop(binding_id, None)
            return _LoopTransfer(current, breaks, continues)
        if isinstance(node, hir.Break):
            return _LoopTransfer(None, {node.loop_levels: [dict(state)]}, {})
        if isinstance(node, hir.Continue):
            return _LoopTransfer(None, {}, {node.loop_levels: [dict(state)]})
        if isinstance(node, hir.Flow) and not any(
            isinstance(arm, hir.LoopArm) for arm in node.arms
        ):
            return self._conditional_transfer(node, state, validate=validate)
        return _LoopTransfer(
            self._analyze(node, state, validate=validate),
            {},
            {},
        )

    def _conditional_transfer(
        self,
        node: hir.Flow,
        state: State,
        *,
        validate: bool,
    ) -> _LoopTransfer:
        remaining: State | None = dict(state)
        normal_exits: list[State] = []
        breaks: dict[int, list[State]] = {}
        continues: dict[int, list[State]] = {}
        for arm in node.arms:
            if remaining is None:
                break
            self._eval(arm.condition, remaining, validate=validate)
            true_state = self._refine(remaining, arm.condition, truth=True)
            if true_state is not None:
                transfer = self._loop_transfer(
                    arm.body,
                    true_state,
                    validate=validate,
                )
                if transfer.normal is not None:
                    normal_exits.append(transfer.normal)
                self._merge_exit_maps(breaks, transfer.breaks)
                self._merge_exit_maps(continues, transfer.continues)
            false_state = self._refine(remaining, arm.condition, truth=False)
            if false_state is None:
                remaining = None
                break
            remaining = false_state
        if node.default is not None and remaining is not None:
            transfer = self._loop_transfer(
                node.default,
                remaining,
                validate=validate,
            )
            if transfer.normal is not None:
                normal_exits.append(transfer.normal)
            self._merge_exit_maps(breaks, transfer.breaks)
            self._merge_exit_maps(continues, transfer.continues)
        elif node.default is None and remaining is not None:
            normal_exits.append(remaining)
        normal = self._join_states(normal_exits) if normal_exits else None
        return _LoopTransfer(normal, breaks, continues)

    @staticmethod
    def _merge_exit_maps(
        target: dict[int, list[State]],
        source: dict[int, list[State]],
    ) -> None:
        for level, states in source.items():
            target.setdefault(level, []).extend(states)

    def _eval(
        self,
        node: hir.AST,
        state: State,
        *,
        validate: bool,
    ) -> Interval | None:
        if isinstance(node, hir.Suppress):
            self._eval(node.item, state, validate=validate)
            return None
        if isinstance(node.type, ty.IntegerLiteralType):
            return Interval.exact(node.type.value)
        if isinstance(node, hir.Integer):
            return Interval.exact(node.value)
        if isinstance(node, hir.ExpressedIdentifier):
            interval = (
                state.get(node.binding_id)
                if node.binding_id is not None
                else None
            )
            if interval is not None:
                return interval
            return self._constant_binding(node.binding_id, set())
        if isinstance(node, hir.Place):
            self._eval(node.target, state, validate=validate)
            root = node.target
            while isinstance(root, (hir.MemberAccess, hir.Index)):
                root = root.value if isinstance(root, hir.MemberAccess) else root.array
            if isinstance(root, hir.ExpressedIdentifier) and root.binding_id is not None:
                state.pop(root.binding_id, None)
            return None
        if isinstance(node, hir.ValueCast):
            inner = self._eval(node.expr, state, validate=validate)
            fitted = self._fit_type(inner, node.type)
            if (
                validate
                and fitted is None
                and node.expr.type in ('int', 'uint')
                and ty.fixed_integer_layout(node.type) is not None
            ):
                # Narrowing an arbitrary-precision integer to a fixed width is
                # only allowed when the analysis proves the value fits.
                self._report_unfit(node, inner, node.type)
            return fitted
        if isinstance(node, hir.RepresentationCast):
            self._eval(node.expr, state, validate=validate)
            return None
        if isinstance(node, hir.Transmute):
            self._eval(node.expr, state, validate=validate)
            return None
        if isinstance(node, hir.ArrayLength):
            self._eval(node.array, state, validate=validate)
            if isinstance(node.array.type, ty.ArrayType):
                length = node.array.type.length
                if length is not None:
                    return Interval.exact(length)
                array_id = _runtime_array_id(node.array)
                if array_id is not None:
                    return state.get(_length_key(array_id), Interval(0, _MAX_LENGTH))
                return Interval(0, _MAX_LENGTH)
            return None
        if isinstance(node, hir.ArrayMethod):
            self._eval(node.array, state, validate=validate)
            return None
        if isinstance(node, hir.DictLookup):
            self._eval(node.key, state, validate=validate)
            return None
        if isinstance(node, hir.DictContains):
            self._eval(node.key, state, validate=validate)
            return None
        if isinstance(node, hir.DictStore):
            self._eval(node.key, state, validate=validate)
            self._eval(node.value, state, validate=validate)
            # A store may append to both hidden arrays.
            for array in (node.keys, node.values):
                array_id = _runtime_array_id(array)
                if array_id is not None:
                    state.pop(_length_key(array_id), None)
                    _drop_index_facts(state, array_id=array_id)
            return None
        if isinstance(node, hir.StringLength):
            self._eval(node.string, state, validate=validate)
            length = self._string_length(node.string.type)
            return None if length is None else Interval.exact(length)
        if isinstance(node, hir.Index):
            self._eval(node.array, state, validate=validate)
            interval = self._eval(node.index, state, validate=validate)
            if validate:
                self._validate_index(node, interval, state)
            return None
        if isinstance(node, hir.IndexAssign):
            self._eval(node.target, state, validate=validate)
            self._eval(node.value, state, validate=validate)
            return None
        if isinstance(node, hir.StringIndex):
            self._eval(node.string, state, validate=validate)
            interval = self._eval(node.index, state, validate=validate)
            if validate:
                self._validate_index(node, interval, state)
            return None
        if isinstance(node, hir.StringSlice):
            self._eval(node.string, state, validate=validate)
            left = (
                Interval.exact(0)
                if node.range.left is None
                else self._eval(node.range.left, state, validate=validate)
            )
            length = self._string_length(node.string.type)
            if node.range.right is None:
                right = None if length is None else Interval.exact(length - 1)
            else:
                right = self._eval(node.range.right, state, validate=validate)
            if validate:
                self._validate_string_slice(node, left, right, length)
            return None
        if isinstance(node, hir.StringEqual):
            self._eval(node.left, state, validate=validate)
            self._eval(node.right, state, validate=validate)
            return None
        if isinstance(node, hir.StringConcat):
            self._eval(node.left, state, validate=validate)
            self._eval(node.right, state, validate=validate)
            return None
        if isinstance(node, hir.InterpolatedString):
            for part in node.parts:
                self._eval(part, state, validate=validate)
            return None
        if isinstance(node, hir.ArrayLiteral):
            for item in node.items:
                self._eval(item, state, validate=validate)
            return None
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod):
            for arg in node.pos_args:
                self._eval(arg, state, validate=validate)
            array_id = _runtime_array_id(node.func.array)
            if array_id is not None:
                key = _length_key(array_id)
                current = state.get(key, Interval(0, _MAX_LENGTH))
                if node.func.name == 'push':
                    state[key] = Interval(
                        _add(current.lower, 1),
                        _minimum_upper(_add(current.upper, 1), _MAX_LENGTH),
                    )
                elif node.func.name == 'pop':
                    state[key] = Interval(
                        max(0, (current.lower or 0) - 1),
                        _subtract(current.upper, 1),
                    )
                    _drop_index_facts(state, array_id=array_id)
                elif node.func.name == 'clear':
                    state[key] = Interval.exact(0)
                    _drop_index_facts(state, array_id=array_id)
            return None
        if isinstance(node, hir.FunctionCall):
            self._eval(node.func, state, validate=validate)
            arguments = [
                self._eval(arg, state, validate=validate)
                for arg in node.pos_args
            ]
            for arg in node.kw_args.values():
                self._eval(arg, state, validate=validate)
            name = (
                node.func.name
                if isinstance(node.func, hir.ExpressedIdentifier)
                else None
            )
            if (
                isinstance(node.func, hir.ExpressedIdentifier)
                and node.func.binding_id is not None
            ):
                for binding_id in self.mutable_globals:
                    state.pop(binding_id, None)
            result: Interval | None = None
            arithmetic = False
            if name == '__unary_sub__' and len(arguments) == 1:
                arithmetic = True
                value = arguments[0]
                if value is not None:
                    result = self._fit_type(
                        Interval(
                            None if value.upper is None else -value.upper,
                            None if value.lower is None else -value.lower,
                        ),
                        node.type,
                    )
            elif len(arguments) == 2 and name in _WORD_ARITHMETIC:
                arithmetic = True
                result = self._binary_interval(
                    name,
                    arguments[0],
                    arguments[1],
                    node.type,
                )
            if validate and arithmetic and node.type in ('int', 'uint'):
                # Abstract integer arithmetic lowers to 64-bit words, so its
                # result must be proven to fit one.
                word = 'int64' if node.type == 'int' else 'uint64'
                if self._fit_type(result, word) is None:
                    self._report_unfit(node, result, word)
            return result
        if isinstance(node, hir.ShortCircuit):
            self._eval(node.left, state, validate=validate)
            self._eval(node.right, state, validate=validate)
            return None
        if isinstance(node, hir.RangeMembership):
            self._eval(node.value, state, validate=validate)
            self._eval(node.range, state, validate=validate)
            return None
        if isinstance(node, hir.Range):
            items = [
                *([] if node.step_pair is None else node.step_pair),
                *([] if node.left is None else [node.left]),
                *([] if node.right is None else [node.right]),
            ]
            seen: set[int] = set()
            for item in items:
                if id(item) in seen:
                    continue
                seen.add(id(item))
                self._eval(item, state, validate=validate)
            return None
        if isinstance(node, hir.IteratorExpression):
            self._eval(node.iterable, state, validate=validate)
            return None
        if isinstance(node, hir.MultiIteratorExpression):
            for iterator in node.iterators:
                self._eval(iterator.iterable, state, validate=validate)
            return None
        if isinstance(node, hir.TypeTest):
            self._eval(node.value, state, validate=validate)
            return None
        if isinstance(node, hir.TypeBlock):
            for item in node.items:
                self._eval(item, state, validate=validate)
            return None
        if isinstance(node, hir.OverloadedFunction):
            for alternate in node.alternates:
                if isinstance(alternate, hir.FunctionLiteral):
                    self._analyze_function(alternate, validate=validate)
            return None
        if isinstance(node, hir.FunctionLiteral):
            self._analyze_function(node, validate=validate, enclosing=state)
            return None
        if isinstance(node, hir.ObjectLiteral):
            for field in node.fields:
                self._eval(field.value, state, validate=validate)
            return None
        if isinstance(node, hir.MemberAccess):
            self._eval(node.value, state, validate=validate)
            return None
        if isinstance(node, hir.MemberAssign):
            self._eval(node.target, state, validate=validate)
            self._eval(node.value, state, validate=validate)
            return None
        if isinstance(node, hir.TypeValue):
            return None
        return None

    def _constant_binding(
        self,
        binding_id: int | None,
        seen: set[int],
    ) -> Interval | None:
        if binding_id is None or binding_id in seen:
            return None
        binding = self.registry.by_id.get(binding_id)
        if (
            binding is None
            or binding.declaration is None
            or binding.declaration.decltype != 'const'
        ):
            return None
        seen.add(binding_id)
        return self._constant_expr(binding.declaration.expr, seen)

    def _constant_expr(
        self,
        node: hir.AST,
        seen: set[int],
    ) -> Interval | None:
        if isinstance(node.type, ty.IntegerLiteralType):
            return Interval.exact(node.type.value)
        if isinstance(node, hir.Integer):
            return Interval.exact(node.value)
        if isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
            return self._constant_expr(node.expr, seen)
        if isinstance(node, hir.ArrayLength) and isinstance(node.array.type, ty.ArrayType):
            length = node.array.type.length
            return None if length is None else Interval.exact(length)
        if isinstance(node, hir.ExpressedIdentifier):
            return self._constant_binding(node.binding_id, seen)
        if not isinstance(node, hir.FunctionCall):
            return None
        name = (
            node.func.name
            if isinstance(node.func, hir.ExpressedIdentifier)
            else None
        )
        arguments = [self._constant_expr(arg, seen) for arg in node.pos_args]
        if len(arguments) == 1 and name == '__unary_sub__':
            value = arguments[0]
            if value is None or value.lower is None:
                return None
            return Interval.exact(-value.lower)
        if len(arguments) == 2 and name is not None:
            return self._binary_interval(name, arguments[0], arguments[1], node.type)
        return None

    def _binary_interval(
        self,
        name: str,
        left: Interval | None,
        right: Interval | None,
        result_type: ty.Type,
    ) -> Interval | None:
        if left is None or right is None:
            return None
        if name == '__add__':
            result = Interval(
                _add(left.lower, right.lower),
                _add(left.upper, right.upper),
            )
        elif name == '__sub__':
            result = Interval(
                _subtract(left.lower, right.upper),
                _subtract(left.upper, right.lower),
            )
        elif name == '__mul__':
            result = _multiply(left, right)
        elif name == '__rshift__':
            # an arithmetic right shift never grows the magnitude
            result = Interval(
                None if left.lower is None else min(left.lower, 0),
                None if left.upper is None else max(left.upper, 0),
            )
        elif name == '__lshift__' and right.lower is not None and right.lower == right.upper:
            result = _multiply(left, Interval.exact(1 << right.lower))
        elif (
            name == '__floordiv__'
            and right.lower is not None
            and right.lower > 0
            and left.lower is not None
            and left.upper is not None
        ):
            # Truncating division by a positive divisor is monotone in the
            # numerator and largest in magnitude at the smallest divisor.
            divisors = [right.lower] if right.upper is None else [right.lower, right.upper]
            candidates = [
                _truncate_divide(numerator, divisor)
                for numerator in (left.lower, left.upper)
                for divisor in divisors
            ]
            result = Interval(min(candidates), max(candidates))
        elif (
            name == '__mod__'
            and right.lower is not None
            and right.lower > 0
            and right.upper is not None
        ):
            result = Interval(0, right.upper - 1)
        else:
            return None
        return self._fit_type(result, result_type)

    def _report_unfit(self, node: hir.AST, interval: Interval | None, word: str) -> None:
        if interval is None or (interval.lower is None and interval.upper is None):
            known = 'no bound on this value is known'
        else:
            lower = '-∞' if interval.lower is None else str(interval.lower)
            upper = '∞' if interval.upper is None else str(interval.upper)
            known = f'the value is only known to lie in [{lower}, {upper}]'
        user_error(
            self.srcfile,
            f'cannot prove this integer fits `{word}`',
            Pointer(span=node.loc, message=f'{known}, so it may not fit 64 bits (neither proven nor refuted)'),
            hint=(
                'unannotated integers are arbitrary precision and only lower to 64-bit words when '
                'the bounds analysis proves they fit: annotate a fixed width such as `int64`, or '
                'establish the range with a comparison'
            ),
        )

    @staticmethod
    def _fit_type(
        interval: Interval | None,
        result_type: ty.Type,
    ) -> Interval | None:
        if interval is None:
            return None
        if not isinstance(result_type, str):
            return interval
        layout = ty.fixed_integer_layout(result_type)
        if layout is None:
            return interval
        width, signed = layout
        minimum = -(1 << (width - 1)) if signed else 0
        maximum = (1 << (width - (1 if signed else 0))) - 1
        if (
            interval.lower is None
            or interval.upper is None
            or interval.lower < minimum
            or interval.upper > maximum
        ):
            return None
        return interval

    @staticmethod
    def _string_length(type_: ty.Type) -> int | None:
        if isinstance(type_, ty.StringLiteralType):
            return ty.string_literal_lengths(type_.value)[2]
        if isinstance(type_, ty.StringType):
            return type_.length
        if isinstance(type_, str) and type_ in {'char', 'grapheme'}:
            return 1
        return None

    def _validate_index(
        self,
        node: hir.Index | hir.StringIndex,
        interval: Interval | None,
        state: State,
    ) -> None:
        if isinstance(node, hir.Index):
            length = (
                node.array.type.length
                if isinstance(node.array.type, ty.ArrayType)
                else None
            )
            index = node.index
            kind = 'array'
        else:
            length = self._string_length(node.string.type)
            index = node.index
            kind = 'string'
        if (
            length is not None
            and interval is not None
            and interval.lower is not None
            and interval.upper is not None
            and 0 <= interval.lower
            and interval.upper < length
        ):
            if interval.lower == interval.upper:
                node.constant_index = interval.lower
            return
        if isinstance(node, hir.Index) and length is None:
            # Runtime-length array: prove `0 <= index` from the interval and
            # `index < length` from either a proven minimum length or an
            # `index <? xs.length` fact about this index binding.
            array_id = _runtime_array_id(node.array)
            nonnegative = interval is not None and interval.lower is not None and interval.lower >= 0
            if array_id is not None and nonnegative:
                minimum_length = state.get(_length_key(array_id), Interval(0, _MAX_LENGTH)).lower or 0
                if interval.upper is not None and interval.upper < minimum_length:
                    if interval.lower == interval.upper:
                        node.constant_index = interval.lower
                    return
                index_id = self._binding_id(index)
                if index_id is not None and _index_fact_key(index_id, array_id) in state:
                    return
        known = (
            'unknown'
            if interval is None
            else f'{interval.lower if interval.lower is not None else "-∞"}'
            f'..{interval.upper if interval.upper is not None else "∞"}'
        )
        user_error(
            self.srcfile,
            f'{kind} index is not proven in bounds',
            Pointer(
                span=index.loc,
                message=f'the index interval here is `{known}`',
            ),
            hint=f'establish both a nonnegative lower bound and an upper bound below the {kind} length',
        )

    def _validate_string_slice(
        self,
        node: hir.StringSlice,
        left: Interval | None,
        right: Interval | None,
        length: int | None,
    ) -> None:
        """Require every possible dynamic endpoint to address a valid boundary."""
        if node.range.left is None and node.range.right is None:
            return
        bounds = node.range.bounds or '[]'

        def shifted(interval: Interval | None, delta: int) -> Interval:
            if interval is None:
                return UNKNOWN_INTERVAL
            return Interval(
                _add(interval.lower, delta),
                _add(interval.upper, delta),
            )

        first = shifted(left, 1 if bounds[0] == '(' else 0)
        last = shifted(right, -1 if bounds[1] == ')' else 0)
        if (
            length is not None
            and first.lower is not None
            and first.upper is not None
            and last.lower is not None
            and last.upper is not None
            and 0 <= first.lower
            and first.upper <= length
            and -1 <= last.lower
            and last.upper < length
        ):
            return

        def describe(interval: Interval) -> str:
            return (
                f'{interval.lower if interval.lower is not None else "-∞"}'
                f'..{interval.upper if interval.upper is not None else "∞"}'
            )

        known_first = describe(first)
        known_last = describe(last)
        user_error(
            self.srcfile,
            'string slice is not proven in bounds',
            Pointer(
                span=node.range.loc,
                message=(
                    f'effective endpoint intervals are `{known_first}` and '
                    f'`{known_last}`'
                ),
            ),
            hint='establish that both endpoints stay within the string boundaries',
        )

    def _refine(
        self,
        state: State,
        condition: hir.AST,
        *,
        truth: bool,
    ) -> State | None:
        refined = dict(state)
        if isinstance(condition, hir.Bool):
            return refined if condition.value == truth else None
        if isinstance(condition, hir.ShortCircuit):
            if condition.op in {'and', 'nand'}:
                effective_truth = truth if condition.op == 'and' else not truth
                if effective_truth:
                    left = self._refine(refined, condition.left, truth=True)
                    if left is None:
                        return None
                    return self._refine(left, condition.right, truth=True)
            if condition.op in {'or', 'nor'}:
                effective_truth = truth if condition.op == 'or' else not truth
                if not effective_truth:
                    left = self._refine(refined, condition.left, truth=False)
                    if left is None:
                        return None
                    return self._refine(left, condition.right, truth=False)
            return refined
        if not (
            isinstance(condition, hir.FunctionCall)
            and isinstance(condition.func, hir.ExpressedIdentifier)
            and len(condition.pos_args) == 2
        ):
            return refined
        name = condition.func.name
        left, right = condition.pos_args
        if truth:
            fact: tuple[int, int] | None = None
            if name == '__lt__':
                index_id = self._binding_id(left)
                array_id = (
                    _runtime_array_id(right.array)
                    if isinstance(right, hir.ArrayLength)
                    else None
                )
                if index_id is not None and array_id is not None:
                    fact = (index_id, array_id)
            elif name == '__gt__':
                index_id = self._binding_id(right)
                array_id = (
                    _runtime_array_id(left.array)
                    if isinstance(left, hir.ArrayLength)
                    else None
                )
                if index_id is not None and array_id is not None:
                    fact = (index_id, array_id)
            if fact is not None:
                refined[_index_fact_key(*fact)] = Interval.exact(1)
        left_binding = self._binding_id(left)
        right_interval = self._eval(right, refined, validate=False)
        if left_binding is not None and right_interval is not None:
            constraint = self._comparison_constraint(name, right_interval, truth)
            if constraint is not None:
                previous = refined.get(left_binding, UNKNOWN_INTERVAL)
                narrowed = previous.intersect(constraint)
                if narrowed.is_empty:
                    return None
                refined[left_binding] = narrowed

        right_binding = self._binding_id(right)
        left_interval = self._eval(left, refined, validate=False)
        inverse = {
            '__lt__': '__gt__',
            '__le__': '__ge__',
            '__gt__': '__lt__',
            '__ge__': '__le__',
            '__eq__': '__eq__',
        }.get(name)
        if (
            right_binding is not None
            and left_interval is not None
            and inverse is not None
        ):
            constraint = self._comparison_constraint(inverse, left_interval, truth)
            if constraint is not None:
                previous = refined.get(right_binding, UNKNOWN_INTERVAL)
                narrowed = previous.intersect(constraint)
                if narrowed.is_empty:
                    return None
                refined[right_binding] = narrowed
        return refined

    @staticmethod
    def _binding_id(node: hir.AST) -> int | None:
        while isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
            node = node.expr
        if isinstance(node, hir.ArrayLength):
            array_id = _runtime_array_id(node.array)
            return None if array_id is None else _length_key(array_id)
        return (
            node.binding_id
            if isinstance(node, hir.ExpressedIdentifier)
            else None
        )

    @staticmethod
    def _comparison_constraint(
        name: str,
        other: Interval,
        truth: bool,
    ) -> Interval | None:
        if name == '__lt__':
            return (
                Interval(None, None if other.upper is None else other.upper - 1)
                if truth
                else Interval(other.lower, None)
            )
        if name == '__le__':
            return (
                Interval(None, other.upper)
                if truth
                else Interval(
                    None if other.lower is None else other.lower + 1,
                    None,
                )
            )
        if name == '__gt__':
            return (
                Interval(
                    None if other.lower is None else other.lower + 1,
                    None,
                )
                if truth
                else Interval(None, other.upper)
            )
        if name == '__ge__':
            return (
                Interval(other.lower, None)
                if truth
                else Interval(
                    None,
                    None if other.upper is None else other.upper - 1,
                )
            )
        if name == '__eq__' and truth:
            return other
        return None

    def _seed_refinements(
        self,
        node: hir.Declare,
        state: State,
        interval: Interval | None,
    ) -> Interval | None:
        """Facts a refined annotation proved at the declaration boundary."""
        assert isinstance(node.annotation, ty.RefinedType) and node.binding_id is not None
        lower: int | None = None
        upper: int | None = None
        length_lower: int | None = None
        for proposition in node.annotation.propositions:
            if proposition.subject == 'self':
                lower = _maximum_lower(lower, proposition.lower_bound())
                upper = _minimum_upper(upper, proposition.upper_bound())
            elif proposition.subject == 'length':
                length_lower = _maximum_lower(length_lower, proposition.lower_bound())
        if lower is not None or upper is not None:
            declared = Interval(lower, upper)
            interval = declared if interval is None else interval.intersect(declared)
        base = ty.strip_refinement(node.annotation)
        if (
            length_lower is not None
            and isinstance(base, ty.ArrayType)
            and base.length is None
            and isinstance(node.expr.type, ty.ArrayType)
            and node.expr.type.length is None
        ):
            key = _length_key(node.binding_id)
            current = state.get(key, Interval(0, _MAX_LENGTH))
            state[key] = current.intersect(Interval(length_lower, _MAX_LENGTH))
        return interval

    @staticmethod
    def _set_interval(
        state: State,
        binding_id: int,
        interval: Interval | None,
    ) -> None:
        if interval is None or interval == UNKNOWN_INTERVAL:
            state.pop(binding_id, None)
        else:
            state[binding_id] = interval

    @staticmethod
    def _join_states(states: list[State]) -> State:
        if not states:
            return {}
        common = set(states[0])
        for state in states[1:]:
            common &= state.keys()
        return {
            binding_id: _union_intervals(
                [state[binding_id] for state in states]
            )
            for binding_id in common
        }

    @staticmethod
    def _widen_states(previous: State, current: State) -> State:
        common = previous.keys() & current.keys()
        return {
            binding_id: previous[binding_id].widen(current[binding_id])
            for binding_id in common
        }


def _union_intervals(intervals: list[Interval]) -> Interval:
    result = intervals[0]
    for interval in intervals[1:]:
        result = result.union(interval)
    return result


def validate_bounds(
    root: hir.Block,
    registry: sb.BindingRegistry,
    srcfile: SrcFile,
) -> None:
    """Validate every dynamic array index against its source-position facts."""

    _BoundsValidator(registry, srcfile, root).validate(root)
