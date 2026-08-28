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
_MAX_LENGTH = (1 << 48) - 1  # more elements than any address space holds; keeps sums of lengths within int64


def _length_key(array_id: int) -> int:
    return -array_id - 1


def _describe_proposition_text(proposition: ty.Proposition) -> str:
    op = proposition.op.replace('not=?', 'not =?')
    subject = proposition.field or ('value' if proposition.subject == 'self' else 'length')
    return f'{subject} {op} {proposition.value}'


def _is_inequality(name: str, truth: bool) -> bool:
    """Whether a comparison outcome says the operands differ."""
    return (name == '__eq__' and not truth) or (name == '__ne__' and truth)


def _exclude_value(interval: Interval, value: int) -> Interval | None:
    """The interval without `value`; None when nothing is left."""
    lower, upper = interval.lower, interval.upper
    if lower is not None and upper is not None and lower == upper == value:
        return None
    if lower is not None and lower == value:
        lower += 1
    if upper is not None and upper == value:
        upper -= 1
    return Interval(lower, upper)


def _is_length_key(key: int) -> bool:
    return key < 0 and key > -_FACT_BASE


def _known_interval(state: State, key: int) -> Interval:
    """The interval a key currently has; lengths default to `[0, _MAX_LENGTH]`."""
    default = Interval(0, _MAX_LENGTH) if _is_length_key(key) else UNKNOWN_INTERVAL
    return state.get(key, default)


def _index_fact_key(index_id: int, array_id: int) -> int:
    return -(_FACT_BASE + (index_id << _FACT_SHIFT) + array_id)


# `x not=? 0` facts are index facts against this pseudo-array: they join,
# widen, and drop on assignment exactly like `i <? xs.length` facts.
_NONZERO_MARK = (1 << _FACT_SHIFT) - 1


def _nonzero_key(binding_id: int) -> int:
    return _index_fact_key(binding_id, _NONZERO_MARK)


def _decode_index_fact(key: int) -> tuple[int, int] | None:
    if key > -_FACT_BASE:
        return None
    raw = -key - _FACT_BASE
    return raw >> _FACT_SHIFT, raw & ((1 << _FACT_SHIFT) - 1)


def _is_runtime_string(type_: ty.Type) -> bool:
    """A string whose grapheme length is only known at runtime."""
    return (isinstance(type_, ty.StringType) and type_.length is None) or type_ == 'string'


def _strip_casts(node: hir.AST) -> hir.AST:
    """Through value/representation casts and obligation wrappers to the value itself."""
    while isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Obligation)):
        node = node.expr if not isinstance(node, hir.Obligation) else node.value
    return node


def _sequence_of(node: hir.AST) -> hir.AST | None:
    """The sequence a `.length` node measures (arrays and strings alike)."""
    if isinstance(node, hir.ArrayLength):
        return node.array
    if isinstance(node, hir.StringLength):
        return node.string
    return None


def _runtime_array_id(node: hir.AST, registry: sb.BindingRegistry | None = None) -> int | None:
    """The fact id of a runtime-length array or string expression (binding or member route)."""
    node = _strip_casts(node)
    if not ((isinstance(node.type, ty.ArrayType) and node.type.length is None) or _is_runtime_string(node.type)):
        return None
    if isinstance(node, hir.ExpressedIdentifier):
        return node.binding_id
    if registry is None:
        return None
    return sb.array_route_id(node, registry)


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
        elif isinstance(value, hir.MemberAssign):
            binding_id = root_binding(value.target)
            if binding_id is not None:
                found.add(binding_id)
        elif isinstance(value, (hir.DictStore, hir.DictRemove)):
            binding_id = root_binding(value.keys)
            if binding_id is not None:
                found.add(binding_id)
        elif isinstance(value, hir.FunctionCall) and isinstance(value.func, hir.DictMethod):
            binding_id = root_binding(value.func.dictionary)
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
        self.unfit: dict[int, tuple[hir.AST, Interval | None, str]] | None = None
        self.checked_functions: set[int] = set()
        assigned = _assigned_binding_ids(root)
        self.assigned = assigned
        # Element intervals of arrays and dictionaries initialized from a
        # literal of constants and never mutated: iterating them bounds the
        # loop variable (`loop [k v] in [3 -> 'Fizz' 5 -> 'Buzz']` gives k in [3, 5]).
        self.element_intervals: dict[tuple[int, str | None], Interval] = {}
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
            if node.binding_id is not None and node.binding_id not in self.assigned:
                self._record_element_intervals(node.binding_id, _strip_casts(node.expr))
            if isinstance(node.annotation, ty.RefinedType) and node.binding_id is not None:
                interval = self._seed_refinements(node, current, interval)
            declared = ty.strip_refinement(node.annotation) if node.annotation is not None else None
            if (
                node.binding_id is not None
                and isinstance(declared, ty.ArrayType)
                and declared.length is None
                and isinstance(node.expr.type, ty.ArrayType)
                and node.expr.type.length is not None
            ):
                # A growable array initialized from an exact-length value starts
                # with that length (the checker keeps the same fact as a refinement).
                current[_length_key(node.binding_id)] = Interval.exact(node.expr.type.length)
            if node.binding_id is not None and isinstance(declared, ty.ObjectType):
                self._seed_field_routes(node.binding_id, declared, node.expr, (), current)
            if node.binding_id is not None and declared is not None and _is_runtime_string(declared):
                # `let s:string = "abc"`: the literal's grapheme count is a fact until `s` is reassigned
                known = self._string_length(_strip_casts(node.expr).type)
                if known is not None:
                    current[_length_key(node.binding_id)] = Interval.exact(known)
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
            if (isinstance(node.target.type, ty.ArrayType) and node.target.type.length is None) or _is_runtime_string(node.target.type):
                # Whole-sequence replacement: nothing is known about the new length.
                current.pop(_length_key(binding_id), None)
                _drop_index_facts(current, array_id=binding_id)
                known = self._string_length(_strip_casts(node.value).type) if _is_runtime_string(node.target.type) else None
                if known is not None:
                    current[_length_key(binding_id)] = Interval.exact(known)
            self._drop_route_facts(current, binding_id)
            return current
        if isinstance(node, hir.IndexAssign):
            self._eval(node.target, current, validate=validate)
            self._eval(node.value, current, validate=validate)
            return current
        if isinstance(node, hir.Flow):
            return self._analyze_flow(node, current, validate=validate)
        if isinstance(node, hir.Assert):
            self._eval(node.condition, current, validate=validate)
            if validate:
                self._validate_assert(node, current)
            if node.runtime:
                return current  # the flow it guards refines the continuation
            held = self._refine(current, node.condition, truth=True)
            return current if held is None else held
        if isinstance(node, hir.Return):
            if node.item is not None:
                self._eval(node.item, current, validate=validate)
            return current
        self._eval(node, current, validate=validate)
        return current

    def _nonzero_proven(self, node: hir.AST, interval: Interval | None, state: State) -> bool:
        """The interval excludes zero, or a `not=? 0` guard covers the binding."""
        if interval is not None and (
            (interval.lower is not None and interval.lower > 0)
            or (interval.upper is not None and interval.upper < 0)
        ):
            return True
        binding = self._binding_id(node)
        return binding is not None and _nonzero_key(binding) in state

    def _validate_divisor(self, divisor: hir.AST, interval: Interval | None, state: State) -> None:
        """`//` and `%` need a divisor proven nonzero (Python raises; Dewy proves)."""
        if self._nonzero_proven(divisor, interval, state):
            return
        source = ' '.join(self.srcfile.body[divisor.loc.start:divisor.loc.stop].split())
        user_error(
            self.srcfile,
            'cannot prove the divisor is nonzero',
            Pointer(span=divisor.loc, message='this may be zero'),
            notes=[f'`{source}` {self._describe_interval(interval, array=False)}'],
            hint='guard the division (`if d not=? 0 { … }`), refine the parameter (`d:int64<i => i not=? 0>`), or check it with `$runtime_assert d not=? 0`',
        )

    def _validate_obligation(self, node: hir.Obligation, interval: Interval | None, state: State) -> None:
        """A refinement the checker could not decide: prove each proposition from facts."""
        for proposition in node.refined.propositions:
            verdict = self._proposition_verdict(proposition, node.value, interval, state)
            if verdict is True:
                continue
            requirement = _describe_proposition_text(proposition)
            source = ' '.join(self.srcfile.body[node.value.loc.start:node.value.loc.stop].split())
            if proposition.field is not None:
                source = f'{source}.{proposition.field}'
            _node, subject_interval = self._subject_interval(proposition, node.value, interval, state)
            user_error(
                self.srcfile,
                'refinement refuted' if verdict is False else 'cannot prove refinement',
                Pointer(
                    span=node.value.loc,
                    message=f'`{requirement}` is required here' if verdict is False else f'no fact establishes `{requirement}` (neither proven nor refuted)',
                ),
                notes=[f'`{source}` {self._describe_interval(subject_interval, array=proposition.subject == "length")}'],
                hint=None if verdict is False else 'establish it with a guard (`if … { }`), or check it with `$runtime_assert`',
            )

    def _length_interval(self, node: hir.AST, state: State) -> Interval | None:
        known = self._string_length(node.type) if not isinstance(node.type, ty.ArrayType) else node.type.length
        if known is not None:
            return Interval.exact(known)
        sequence_id = _runtime_array_id(node, self.registry)
        if sequence_id is None:
            return None
        return state.get(_length_key(sequence_id), Interval(0, _MAX_LENGTH))

    def _field_node(self, value: hir.AST, field: str) -> hir.AST:
        """`value.field` as a node: the literal's field, or a member access (tracked by route)."""
        literal = _strip_casts(value)
        if isinstance(literal, hir.ObjectLiteral):
            for item in literal.fields:
                if item.name == field:
                    return item.value
        return hir.MemberAccess(value.loc, 'int64', literal, field, True)

    def _subject_interval(self, proposition: ty.Proposition, value: hir.AST, interval: Interval | None, state: State) -> tuple[hir.AST, Interval | None]:
        """The node and interval a proposition's subject denotes for ``value``."""
        if (field := proposition.field) is not None:
            node = self._field_node(value, field)
            return node, self._eval(node, state, validate=False)
        if proposition.subject == 'self':
            return value, interval
        return value, self._length_interval(value, state)

    def _proposition_verdict(self, proposition: ty.Proposition, value: hir.AST, interval: Interval | None, state: State) -> bool | None:
        """True when the facts prove the proposition, False when they refute it, None otherwise."""
        subject_node, subject = self._subject_interval(proposition, value, interval, state)
        constant = Interval.exact(proposition.value)
        name = {'>?': '__gt__', '>=?': '__ge__', '<?': '__lt__', '<=?': '__le__', '=?': '__eq__', 'not=?': '__ne__'}.get(proposition.op)
        if name is None:
            return None
        decided = self._decide_comparison(name, subject, constant)
        if decided is not None:
            return decided
        if name == '__ne__' and proposition.value == 0 and proposition.subject != 'length':
            return True if self._nonzero_proven(subject_node, subject, state) else None
        return None

    def _seed_parameter_refinements(self, function: hir.FunctionLiteral, state: State) -> None:
        """Inside the body a refined parameter's propositions are facts."""
        param_loc = function.loc
        for param in [*function.pos_or_kw_args, *function.kw_only_args]:
            if not isinstance(param.type, ty.RefinedType) or param.binding_id is None:
                continue
            lower: int | None = None
            upper: int | None = None
            for proposition in param.type.propositions:
                if (field := proposition.field) is not None:
                    # `r:Ratio<bottom >? 0>`: a fact on the field's member route
                    base = ty.unfold(param.type.base)
                    declared = base.field(field) if isinstance(base, ty.ObjectType) else None
                    route_id = self.registry.route_id(param.binding_id, (field,), declared.type if declared is not None else 'int64', param_loc)
                    field_lower, field_upper = proposition.lower_bound(), proposition.upper_bound()
                    if field_lower is not None or field_upper is not None:
                        current = state.get(route_id, UNKNOWN_INTERVAL)
                        state[route_id] = current.intersect(Interval(field_lower, field_upper))
                    if proposition.op == 'not=?' and proposition.value == 0:
                        state[_nonzero_key(route_id)] = Interval.exact(1)
                    continue
                if proposition.subject == 'self':
                    lower = _maximum_lower(lower, proposition.lower_bound())
                    upper = _minimum_upper(upper, proposition.upper_bound())
                    if proposition.op == 'not=?' and proposition.value == 0:
                        state[_nonzero_key(param.binding_id)] = Interval.exact(1)
                elif proposition.subject == 'length':
                    minimum = proposition.lower_bound()
                    if minimum is not None:
                        key = _length_key(param.binding_id)
                        state[key] = state.get(key, Interval(0, _MAX_LENGTH)).intersect(Interval(minimum, _MAX_LENGTH))
            if lower is not None or upper is not None:
                self._set_interval(state, param.binding_id, Interval(lower, upper))

    def _validate_assert(self, node: hir.Assert, state: State) -> None:
        """`$assert` is proven when its false path is impossible, refuted when its true path is."""
        if self._refine(state, node.condition, truth=False) is None:
            return
        refuted = self._refine(state, node.condition, truth=True) is None
        if node.runtime and not refuted:
            return
        if node.message is not None:
            detail = node.message
        elif refuted:
            detail = 'this condition is false for every value the analysis admits'
        else:
            detail = 'no compile-time fact establishes this condition (neither proven nor refuted)'
        user_error(
            self.srcfile,
            'assertion refuted' if refuted else 'cannot prove assertion',
            Pointer(span=node.condition.loc, message=detail),
            notes=self._explain_condition(node.condition, state),
            dimmed=[node.dimmed] if node.dimmed is not None else None,
            hint=None if refuted else 'check it at runtime with `$runtime_assert`, or establish the fact with a guard',
        )

    def _explain_condition(self, condition: hir.AST, state: State) -> list[str]:
        """What the analysis knows about each operand, and what that decides for each comparison."""
        lines: list[str] = []
        described: set[str] = set()

        def source(node: hir.AST) -> str:
            return ' '.join(self.srcfile.body[node.loc.start:node.loc.stop].split())

        def describe_operand(node: hir.AST) -> None:
            if isinstance(node, (hir.Integer, hir.Bool, hir.String)):
                return
            text = source(node)
            if text in described:
                return
            described.add(text)
            interval = self._eval(node, state, validate=False)
            lines.append(f'`{text}` {self._describe_interval(interval, array=_sequence_of(node) is not None)}')

        def verdict(node: hir.AST) -> str:
            if self._refine(state, node, truth=True) is None:
                return 'so `{}` is false'
            if self._refine(state, node, truth=False) is None:
                return 'so `{}` holds'
            return '`{}` cannot be decided from these facts'

        def visit(node: hir.AST) -> None:
            if isinstance(node, hir.ShortCircuit):
                visit(node.left)
                visit(node.right)
                return
            if (
                isinstance(node, hir.FunctionCall)
                and isinstance(node.func, hir.ExpressedIdentifier)
                and node.func.name in {'__lt__', '__le__', '__gt__', '__ge__', '__eq__', '__ne__'}
                and len(node.pos_args) == 2
            ):
                for operand in node.pos_args:
                    describe_operand(operand)
                lines.append(verdict(node).format(source(node)))
                return
            lines.append(verdict(node).format(source(node)))

        visit(condition)
        return lines

    @staticmethod
    def _describe_interval(interval: Interval | None, *, array: bool) -> str:
        if interval is None or (interval.lower is None and interval.upper is None):
            return 'has no known bound' if not array else 'is a runtime length the analysis knows nothing about'
        if array and interval.lower is not None and (interval.upper is None or interval.upper >= (1 << 48) - 1):
            # the address-space cap is not a fact worth showing
            return f'is a runtime length of at least {interval.lower}'
        if interval.lower is not None and interval.lower == interval.upper:
            return (
                f'is {interval.lower} (the array has exactly {interval.lower} elements)'
                if array else f'is {interval.lower}'
            )
        if interval.lower is not None and interval.upper is not None:
            return f'lies in [{interval.lower}, {interval.upper}]'
        if interval.lower is not None:
            return (
                f'is at least {interval.lower} (the array has at least {interval.lower} elements)'
                if array else f'is at least {interval.lower}'
            )
        return f'is at most {interval.upper}'

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
        self._seed_parameter_refinements(function, state)
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
                exit_state = self._analyze(arm.body, true_state, validate=validate)
                if arm.body.type != ty.BOTTOM_TYPE:  # a diverging arm never reaches the continuation
                    exits.append(exit_state)
            false_state = self._refine(remaining, arm.condition, truth=False)
            if false_state is None:
                remaining = None
                break
            remaining = false_state
        if node.default is not None and remaining is not None:
            exit_state = self._analyze(node.default, remaining, validate=validate)
            if node.default.type != ty.BOTTOM_TYPE:
                exits.append(exit_state)
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

    def _iterator_interval(self, iterator: hir.IteratorExpression) -> Interval:
        if isinstance(iterator.iterable.type, ty.ArrayType):
            target_type = ty.optional_payload(iterator.target.type)
            if target_type is None:
                target_type = iterator.target.type
            layout = ty.fixed_integer_layout(target_type)
            if layout is None:
                return UNKNOWN_INTERVAL
            width, signed = layout
            type_range = (
                Interval(-(1 << (width - 1)), (1 << (width - 1)) - 1)
                if signed
                else Interval(0, (1 << width) - 1)
            )
            elements = self._iterable_element_interval(iterator.iterable)
            return type_range if elements is None else type_range.intersect(elements)
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

    def _literal_element_interval(self, literal: hir.AST) -> Interval | None:
        """The union of an array literal's constant elements, when every element is one."""
        literal = _strip_casts(literal)
        if not isinstance(literal, hir.ArrayLiteral) or not literal.items:
            return None
        result: Interval | None = None
        for item in literal.items:
            if isinstance(item, hir.Spread):
                return None
            constant = self._constant_expr(_strip_casts(item), set())
            if constant is None or constant.lower is None or constant.upper is None:
                return None
            result = constant if result is None else result.union(constant)
        return result

    def _record_element_intervals(self, binding_id: int, expr: hir.AST) -> None:
        """Remember the constant elements a never-mutated array or dictionary was built from."""
        elements = self._literal_element_interval(expr)
        if elements is not None:
            self.element_intervals[(binding_id, None)] = elements
            return
        if isinstance(expr, hir.ObjectLiteral) and isinstance(expr.type, ty.ObjectType) and expr.type.brand == 'dict':
            for field in expr.fields:
                if field.name in ('keys', 'values'):
                    part = self._literal_element_interval(field.value)
                    if part is not None:
                        self.element_intervals[(binding_id, field.name)] = part

    def _iterable_element_interval(self, iterable: hir.AST) -> Interval | None:
        """Bounds on the elements an iteration yields, from a literal or a never-mutated binding."""
        iterable = _strip_casts(iterable)
        direct = self._literal_element_interval(iterable)
        if direct is not None:
            return direct
        if isinstance(iterable, hir.ExpressedIdentifier) and iterable.binding_id is not None:
            return self.element_intervals.get((iterable.binding_id, None))
        if isinstance(iterable, hir.DictEntries):
            dictionary = _strip_casts(iterable.dictionary)
            if isinstance(dictionary, hir.ExpressedIdentifier) and dictionary.binding_id is not None:
                return self.element_intervals.get((dictionary.binding_id, iterable.name))
        return None

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
        normal = self._analyze(node, state, validate=validate)
        return _LoopTransfer(
            None if node.type == ty.BOTTOM_TYPE else normal,  # `return` leaves the loop without a normal exit
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
        if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            return self._eval(node.items[0], state, validate=validate)  # parentheses
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
                array_id = _runtime_array_id(node.array, self.registry)
                if array_id is not None:
                    return state.get(_length_key(array_id), Interval(0, _MAX_LENGTH))
                return Interval(0, _MAX_LENGTH)
            return None
        if isinstance(node, hir.ArrayMethod):
            self._eval(node.array, state, validate=validate)
            return None
        if isinstance(node, hir.DictLookup):
            self._eval(node.key, state, validate=validate)
            if node.default is not None:
                self._eval(node.default, state, validate=validate)
            return None
        if isinstance(node, hir.DictContains):
            self._eval(node.key, state, validate=validate)
            return None
        if isinstance(node, hir.DictRemove):
            if node.key is not None:
                self._eval(node.key, state, validate=validate)
            if node.default is not None:
                self._eval(node.default, state, validate=validate)
            for array in (node.keys, *([node.values] if node.values is not None else [])):
                array_id = _runtime_array_id(array, self.registry)
                if array_id is not None:
                    key = _length_key(array_id)
                    if node.key is None:
                        state[key] = Interval.exact(0)
                    else:
                        state.pop(key, None)  # tombstone now, compaction later
                    _drop_index_facts(state, array_id=array_id)
            return None
        if isinstance(node, hir.DictEntries):
            self._eval(node.dictionary, state, validate=validate)
            return None
        if isinstance(node, hir.SetAlgebra):
            self._eval(node.left, state, validate=validate)
            self._eval(node.right, state, validate=validate)
            return None
        if isinstance(node, hir.DictView):
            self._eval(node.dictionary, state, validate=validate)
            return None
        if isinstance(node, hir.DictStore):
            self._eval(node.key, state, validate=validate)
            if node.value is not None:
                self._eval(node.value, state, validate=validate)
            # A store may append to both hidden arrays.
            for array in (node.keys, *([node.values] if node.values is not None else [])):
                array_id = _runtime_array_id(array, self.registry)
                if array_id is not None:
                    state.pop(_length_key(array_id), None)
                    _drop_index_facts(state, array_id=array_id)
            return None
        if isinstance(node, hir.Obligation):
            interval = self._eval(node.value, state, validate=validate)
            if validate:
                self._validate_obligation(node, interval, state)
            return interval
        if isinstance(node, hir.StringLength):
            self._eval(node.string, state, validate=validate)
            length = self._string_length(node.string.type)
            if length is not None:
                return Interval.exact(length)
            string_id = _runtime_array_id(node.string, self.registry)
            if string_id is not None:
                return state.get(_length_key(string_id), Interval(0, _MAX_LENGTH))
            return Interval(0, _MAX_LENGTH)
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
                self._validate_string_slice(node, left, right, length, state)
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
        if isinstance(node, hir.Spread):
            self._eval(node.value, state, validate=validate)
            return None
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod):
            arguments = [self._eval(arg, state, validate=validate) for arg in node.pos_args]
            keyword_arguments = {
                name: self._eval(arg, state, validate=validate) for name, arg in node.kw_args.items()
            }
            array_id = _runtime_array_id(node.func.array, self.registry)
            name = node.func.name
            if name == 'pop':
                index_arg = node.pos_args[0] if node.pos_args else node.kw_args.get('idx')
                index_interval = arguments[0] if arguments else keyword_arguments.get('idx')
            elif name == 'insert':
                index_arg = node.pos_args[1] if len(node.pos_args) > 1 else node.kw_args.get('idx')
                index_interval = arguments[1] if len(arguments) > 1 else keyword_arguments.get('idx')
            elif name == 'truncate':
                index_arg = node.pos_args[0] if node.pos_args else node.kw_args.get('count')
                index_interval = arguments[0] if arguments else keyword_arguments.get('count')
            else:
                index_arg = None
                index_interval = None
            if array_id is not None:
                key = _length_key(array_id)
                current = state.get(key, Interval(0, _MAX_LENGTH))
                if validate and index_arg is not None and name in {'pop', 'insert'}:
                    self._validate_method_index(
                        node, index_arg, index_interval, state, array_id, current,
                        allow_end=name == 'insert',
                    )
                if name in {'push', 'insert'}:
                    state[key] = Interval(
                        _add(current.lower, 1),
                        _minimum_upper(_add(current.upper, 1), _MAX_LENGTH),
                    )
                elif name == 'pop':
                    state[key] = Interval(
                        max(0, (current.lower or 0) - 1),
                        _subtract(current.upper, 1),
                    )
                    _drop_index_facts(state, array_id=array_id)
                elif name == 'truncate':
                    cap_lower = 0 if index_interval is None or index_interval.lower is None else max(index_interval.lower, 0)
                    cap_upper = None if index_interval is None else index_interval.upper
                    state[key] = Interval(
                        min(current.lower or 0, cap_lower),
                        _minimum_upper(current.upper, cap_upper),
                    )
                    _drop_index_facts(state, array_id=array_id)
                elif name == 'clear':
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
                if validate and name in ('__floordiv__', '__mod__'):
                    self._validate_divisor(node.pos_args[1], arguments[1], state)
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
            # the right operand only runs when the left decided nothing yet:
            # under `and` the left was true, under `or` it was false
            if node.op in {'and', 'nand'}:
                right_state = self._refine(state, node.left, truth=True)
            elif node.op in {'or', 'nor'}:
                right_state = self._refine(state, node.left, truth=False)
            else:
                right_state = dict(state)
            if right_state is not None:
                self._eval(node.right, right_state, validate=validate)
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
            route_id = sb.array_route_id(node, self.registry)
            return state.get(route_id) if route_id is not None else None
        if isinstance(node, hir.MemberAssign):
            self._eval(node.target, state, validate=validate)
            value = self._eval(node.value, state, validate=validate)
            assigned = sb.member_path(node.target)
            if assigned is not None:
                root_id, path = assigned
                self._drop_route_facts(state, root_id, path)
                route_id = sb.array_route_id(node.target, self.registry)
                if route_id is not None:
                    self._set_interval(state, route_id, value)  # the field now holds the assigned value
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
        if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            return self._constant_expr(node.items[0], seen)  # parentheses
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

    def _seed_field_routes(
        self,
        root_id: int,
        declared: ty.ObjectType,
        expr: hir.AST,
        path: tuple[str, ...],
        state: State,
    ) -> None:
        """Growable array fields initialized by an object literal start with the literal's length."""
        literal = expr
        while isinstance(literal, (hir.RepresentationCast, hir.ValueCast)) or (
            isinstance(literal, hir.Block) and not literal.scoped and len(literal.items) == 1
        ):
            literal = literal.expr if isinstance(literal, (hir.RepresentationCast, hir.ValueCast)) else literal.items[0]
        if not isinstance(literal, hir.ObjectLiteral):
            return
        for field_value in literal.fields:
            field = declared.field(field_value.name)
            if field is None:
                continue
            field_path = (*path, field_value.name)
            if (
                isinstance(field.type, ty.ArrayType)
                and field.type.length is None
                and isinstance(field_value.value.type, ty.ArrayType)
                and field_value.value.type.length is not None
            ):
                route_id = self.registry.route_id(root_id, field_path, field.type, field_value.loc)
                state[_length_key(route_id)] = Interval.exact(field_value.value.type.length)
            elif isinstance(field.type, ty.ObjectType):
                self._seed_field_routes(root_id, field.type, field_value.value, field_path, state)
            elif isinstance(field.type, str) and ty.fixed_integer_layout(field.type) is not None:
                # an integer field starts with its initializer's interval (`bottom=2`, `bottom=d`)
                interval = self._eval(field_value.value, state, validate=False)
                if interval is not None and interval != UNKNOWN_INTERVAL:
                    route_id = self.registry.route_id(root_id, field_path, field.type, field_value.loc)
                    state[route_id] = interval

    def _drop_route_facts(self, state: State, root_id: int, prefix: tuple[str, ...] = ()) -> None:
        """Member routes under a reassigned binding or field lose their length and index facts."""
        for route_id in self.registry.routes_under(root_id, prefix):
            state.pop(route_id, None)
            state.pop(_length_key(route_id), None)
            _drop_index_facts(state, array_id=route_id)
            _drop_index_facts(state, index_id=route_id)

    def _report_unfit(self, node: hir.AST, interval: Interval | None, word: str) -> None:
        if self.unfit is not None:
            # the representation pass gives this value a big integer instead
            self.unfit[id(node)] = (node, interval, word)
            return
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

    def _refine_after(self, state: State, left: hir.AST, right: hir.AST, *, right_truth: bool) -> State | None:
        """Refine by `right` on the path where `left` decided nothing (its truth is the opposite of `right_truth`)."""
        first = self._refine(state, left, truth=not right_truth)
        if first is None:
            return None
        return self._refine(first, right, truth=right_truth)

    def _join_alternatives(self, first: State | None, second: State | None) -> State | None:
        """The state after either of two possible paths (None marks an impossible path)."""
        alternatives = [state for state in (first, second) if state is not None]
        if not alternatives:
            return None
        return self._join_states(alternatives)

    def _length_offset_index(self, index: hir.AST, array_id: int) -> int | None:
        """`k` when the index is `xs.length - k` for the same sequence with a constant `k >= 1`.

        Subtraction chains fold: `xs.length - 1 - 1` (`end - 1`) is `k = 2`.
        """
        while isinstance(index, (hir.ValueCast, hir.RepresentationCast)):
            index = index.expr
        if not (
            isinstance(index, hir.FunctionCall)
            and isinstance(index.func, hir.ExpressedIdentifier)
            and index.func.name == '__sub__'
            and len(index.pos_args) == 2
        ):
            return None
        left, right = index.pos_args
        constant = self._constant_expr(right, set())
        if constant is None or constant.lower is None or constant.lower != constant.upper or constant.lower < 0:
            return None
        measured = _sequence_of(left)
        if measured is not None:
            if _runtime_array_id(measured, self.registry) != array_id:
                return None
            inner = 0
        else:
            inner_offset = self._length_offset_index(left, array_id)
            if inner_offset is None:
                return None
            inner = inner_offset
        total = inner + constant.lower
        return total if total >= 1 else None

    def _validate_method_index(
        self,
        node: hir.FunctionCall,
        index: hir.AST,
        interval: Interval | None,
        state: State,
        array_id: int,
        length: Interval,
        *,
        allow_end: bool,
    ) -> None:
        """Prove `0 <= idx < length` for `pop(idx)` (or `<= length` for `insert`)."""
        nonnegative = interval is not None and interval.lower is not None and interval.lower >= 0
        if nonnegative:
            minimum_length = length.lower or 0
            limit = minimum_length + (1 if allow_end else 0)
            if interval.upper is not None and interval.upper < limit:
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
            f'`{node.func.name}` index is not proven in bounds',
            Pointer(span=index.loc, message=f'the index interval here is `{known}`'),
            hint=(
                'establish a nonnegative lower bound and an upper bound '
                + ('at or below' if allow_end else 'below')
                + ' the array length (for example `if idx <? xs.length { ... }`)'
            ),
        )

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
        if length is None:
            # Runtime-length array or string: prove `0 <= index` from the
            # interval and `index < length` from either a proven minimum
            # length or an `index <? xs.length` fact about this index binding.
            array_id = _runtime_array_id(node.array if isinstance(node, hir.Index) else node.string, self.registry)
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
                # `xs[xs.length - k]` is in bounds when the length is at least k
                offset = self._length_offset_index(index, array_id)
                if offset is not None and minimum_length >= offset:
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
        state: State | None = None,
    ) -> None:
        """Require every possible dynamic endpoint to address a valid boundary.

        A runtime-length string uses its facts: a proven minimum length, or
        `i <? s.length` facts about the endpoint bindings.
        """
        if node.range.left is None and node.range.right is None:
            return
        bounds = node.range.bounds or '[]'
        if length is None and state is not None:
            string_id = _runtime_array_id(node.string, self.registry)
            if string_id is not None:
                minimum = state.get(_length_key(string_id), Interval(0, _MAX_LENGTH)).lower or 0

                def endpoint_proven(endpoint: hir.AST | None, interval: Interval | None, delta: int, limit: int) -> bool:
                    """`endpoint + delta` lies in `[-1 or 0, limit)` for every value, or an index fact bounds it."""
                    if endpoint is None:
                        return True
                    if interval is None or interval.lower is None or interval.lower + delta < (0 if delta >= 0 else -1):
                        return False
                    if interval.upper is not None and interval.upper + delta < limit:
                        return True
                    binding = self._binding_id(endpoint)
                    if binding is not None and _index_fact_key(binding, string_id) in state:
                        return True
                    # `s.length - k` (`end`, `end - 1`): below the length by construction,
                    # nonnegative when the length is at least k (minus the shift)
                    offset = self._length_offset_index(endpoint, string_id)
                    if offset is None:
                        return False
                    effective = offset - delta  # the endpoint is `length - effective`
                    lowest = -1 if limit == minimum else 0  # a last endpoint may be -1 (an empty slice)
                    return effective >= 1 and minimum - effective >= lowest

                first_ok = endpoint_proven(node.range.left, left, 1 if bounds[0] == '(' else 0, minimum + 1)
                last_ok = endpoint_proven(node.range.right, right, -1 if bounds[1] == ')' else 0, minimum)
                if first_ok and last_ok:
                    return

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
                # `a and b` false: either `a` was false, or `a` held and `b` was false
                return self._join_alternatives(
                    self._refine(refined, condition.left, truth=False),
                    self._refine_after(refined, condition.left, condition.right, right_truth=False),
                )
            if condition.op in {'or', 'nor'}:
                effective_truth = truth if condition.op == 'or' else not truth
                if not effective_truth:
                    left = self._refine(refined, condition.left, truth=False)
                    if left is None:
                        return None
                    return self._refine(left, condition.right, truth=False)
                # `a or b` true: either `a` held, or `a` was false and `b` held
                return self._join_alternatives(
                    self._refine(refined, condition.left, truth=True),
                    self._refine_after(refined, condition.left, condition.right, right_truth=True),
                )
            return refined
        if not (
            isinstance(condition, hir.FunctionCall)
            and isinstance(condition.func, hir.ExpressedIdentifier)
            and len(condition.pos_args) == 2
        ):
            return refined
        name = condition.func.name
        left, right = condition.pos_args
        decided = self._decide_comparison(
            name,
            self._eval(left, refined, validate=False),
            self._eval(right, refined, validate=False),
        )
        if decided is not None and decided != truth:
            return None  # the operand intervals settle the comparison: this path is impossible
        # `i <? xs.length` holding, or `i >=? xs.length` failing, is the same index fact
        settled = name if truth else {'__ge__': '__lt__', '__le__': '__gt__'}.get(name)
        if settled in {'__lt__', '__gt__'}:
            fact: tuple[int, int] | None = None
            if settled == '__lt__':
                index_id = self._binding_id(left)
                measured = _sequence_of(right)
                array_id = _runtime_array_id(measured, self.registry) if measured is not None else None
                if index_id is not None and array_id is not None:
                    fact = (index_id, array_id)
            else:
                index_id = self._binding_id(right)
                measured = _sequence_of(left)
                array_id = _runtime_array_id(measured, self.registry) if measured is not None else None
                if index_id is not None and array_id is not None:
                    fact = (index_id, array_id)
            if fact is not None:
                refined[_index_fact_key(*fact)] = Interval.exact(1)
        left_binding = self._binding_id(left)
        right_interval = self._eval(right, refined, validate=False)
        if _is_inequality(name, truth):
            # `x not=? 0` (or a failed `x =? 0`): a nonzero fact on the binding
            for side, other in ((left, right), (right, left)):
                side_binding = self._binding_id(side)
                other_interval = self._eval(other, refined, validate=False)
                if side_binding is not None and other_interval is not None and other_interval.lower == 0 and other_interval.upper == 0:
                    refined[_nonzero_key(side_binding)] = Interval.exact(1)
        if left_binding is not None and right_interval is not None:
            constraint = self._comparison_constraint(name, right_interval, truth)
            if constraint is not None:
                previous = _known_interval(refined, left_binding)
                narrowed = previous.intersect(constraint)
                if narrowed.is_empty:
                    return None
                refined[left_binding] = narrowed
            elif _is_inequality(name, truth) and right_interval.lower is not None and right_interval.lower == right_interval.upper:
                # `x not =? c` (or a failed `x =? c`) excludes `c`: it tightens a bound it sits on
                excluded = _exclude_value(_known_interval(refined, left_binding), right_interval.lower)
                if excluded is None:
                    return None
                refined[left_binding] = excluded

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
                previous = _known_interval(refined, right_binding)
                narrowed = previous.intersect(constraint)
                if narrowed.is_empty:
                    return None
                refined[right_binding] = narrowed
            elif _is_inequality(inverse, truth) and left_interval.lower is not None and left_interval.lower == left_interval.upper:
                excluded = _exclude_value(_known_interval(refined, right_binding), left_interval.lower)
                if excluded is None:
                    return None
                refined[right_binding] = excluded
        return refined

    def _binding_id(self, node: hir.AST) -> int | None:
        while isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
            node = node.expr
        measured = _sequence_of(node)
        if measured is not None:
            array_id = _runtime_array_id(measured, self.registry)
            return None if array_id is None else _length_key(array_id)
        if isinstance(node, hir.ExpressedIdentifier):
            return node.binding_id
        if isinstance(node, hir.MemberAccess):
            # a field of a named object (`value.denominator`) is a route:
            # guards refine it until the field or its root is assigned
            return sb.array_route_id(node, self.registry)
        return None

    @staticmethod
    def _decide_comparison(name: str, left: Interval | None, right: Interval | None) -> bool | None:
        """The comparison's outcome when the operand intervals settle it either way."""
        if left is None or right is None:
            return None

        def less(a: Interval, b: Interval, *, strict: bool) -> bool | None:
            if a.upper is not None and b.lower is not None and (a.upper < b.lower if strict else a.upper <= b.lower):
                return True
            if a.lower is not None and b.upper is not None and (a.lower >= b.upper if strict else a.lower > b.upper):
                return False
            return None

        if name == '__lt__':
            return less(left, right, strict=True)
        if name == '__gt__':
            return less(right, left, strict=True)
        if name == '__le__':
            return less(left, right, strict=False)
        if name == '__ge__':
            return less(right, left, strict=False)
        if name in {'__eq__', '__ne__'}:
            exact = (
                left.lower is not None and left.lower == left.upper
                and right.lower is not None and right.lower == right.upper
            )
            if exact:
                equal = left.lower == right.lower
            elif less(left, right, strict=True) is True or less(right, left, strict=True) is True:
                equal = False
            else:
                return None
            return equal if name == '__eq__' else not equal
        return None

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
        widened: State = {}
        for binding_id in common:
            interval = previous[binding_id].widen(current[binding_id])
            if _is_length_key(binding_id):
                # array lengths never leave [0, _MAX_LENGTH], even when widened
                interval = Interval(
                    0 if interval.lower is None else interval.lower,
                    _MAX_LENGTH if interval.upper is None else interval.upper,
                )
            widened[binding_id] = interval
        return widened


def _union_intervals(intervals: list[Interval]) -> Interval:
    result = intervals[0]
    for interval in intervals[1:]:
        result = result.union(interval)
    return result


def validate_bounds(
    root: hir.Block,
    registry: sb.BindingRegistry,
    srcfile: SrcFile,
    unfit: dict[int, tuple[hir.AST, Interval | None, str]] | None = None,
) -> None:
    """Validate every dynamic array index against its source-position facts.

    With ``unfit`` given, abstract-integer values that cannot be proven to fit
    a 64-bit word are collected there (keyed by node id) for the representation
    pass instead of being reported as errors.
    """

    validator = _BoundsValidator(registry, srcfile, root)
    validator.unfit = unfit
    validator.validate(root)
