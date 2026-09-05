"""Flow-sensitive integer bounds validation for checked HIR."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ...reporting import Error, Pointer, Span, SrcFile
from ...targets import ADDRESS_BITS, max_length
from .. import bindings as sb
from .. import hir, ty
from ..errors import UserError, user_error, user_warning
from ..hir_display import type_to_dewy


@dataclass(frozen=True)
class Interval:
    """An inclusive integer interval; ``None`` denotes an infinite endpoint."""

    lower: int | None
    upper: int | None
    capped: bool = field(default=False, compare=False)
    """Whether an endpoint descends from the target's length cap (see `targets.max_length`)
    rather than from a fact of the program: a proof that needs such an endpoint rests on the
    address-space axiom, and `dewy analyze` says so."""

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
        return Interval(lower, upper, capped=self.capped or other.capped)

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
        return Interval(lower, upper, capped=self.capped or other.capped)

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
        return Interval(lower, upper, capped=self.capped or other.capped)


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
_MAX_LENGTH = max_length('x86_64')  # the default cap; the validator carries its target's (`targets.max_length`)


@dataclass(frozen=True)
class CapNote:
    """A proof that rests on the target's length cap rather than on a fact of the program."""

    srcfile: SrcFile
    loc: Span
    message: str


last_cap_notes: list[CapNote] = []


def _length_key(array_id: int) -> int:
    return -array_id - 1


def _propositions_interval(propositions: tuple[ty.Proposition, ...] | list[ty.Proposition]) -> Interval | None:
    """The bounds a set of value propositions guarantees (`>? 0` is `[1, ∞]`)."""
    lower: int | None = None
    upper: int | None = None
    for proposition in propositions:
        if proposition.subject != 'self':
            continue
        lower = _maximum_lower(lower, proposition.lower_bound())
        upper = _minimum_upper(upper, proposition.upper_bound())
    return None if lower is None and upper is None else Interval(lower, upper)


def _length_propositions_interval(propositions: tuple[ty.Proposition, ...] | list[ty.Proposition]) -> Interval | None:
    """The bounds a set of length propositions (`length >? 0` on a field) guarantees."""
    lower: int | None = None
    upper: int | None = None
    for proposition in propositions:
        if proposition.subject != 'length':
            continue
        lower = _maximum_lower(lower, proposition.lower_bound())
        upper = _minimum_upper(upper, proposition.upper_bound())
    return None if lower is None and upper is None else Interval(lower, upper)


def _excludes_zero(propositions: tuple[ty.Proposition, ...] | list[ty.Proposition]) -> bool:
    return any(p.subject == 'self' and p.op == 'not=?' and p.value == 0 for p in propositions)


def _call_function_type(node: hir.AST) -> ty.FunctionType | None:
    """The function type a call invokes (the selected overload), if the node is a call."""
    node = _strip_casts(node)
    if isinstance(node, hir.FunctionCall):
        function_type = node.func.type
        if isinstance(function_type, ty.OverloadType) and node.selected_method_index is not None:
            function_type = function_type.methods[node.selected_method_index]
        if isinstance(function_type, ty.FunctionType):
            return function_type
    return None


def _call_result_refinement(node: hir.AST) -> ty.RefinedType | None:
    """The refined return type of a call (`f():>int64<i => i >=? 1>`), if any."""
    function_type = _call_function_type(node)
    if function_type is not None and isinstance(function_type.ret, ty.RefinedType):
        return function_type.ret
    return None


def _call_result_refinements(node: hir.AST) -> list[ty.RefinedType]:
    """The refined members of a call's result type (`uint64<…> | none` has one)."""
    function_type = _call_function_type(node)
    if function_type is None:
        return []
    if isinstance(function_type.ret, ty.RefinedType):
        return [function_type.ret]
    if isinstance(function_type.ret, ty.TypeOr):
        return [item for item in function_type.ret.items if isinstance(item, ty.RefinedType)]
    return []


def _call_argument(node: hir.AST, name: str) -> hir.AST | None:
    """The argument a call passes for the parameter `name`, positionally or by keyword."""
    function_type = _call_function_type(node)
    call = _strip_casts(node)
    if function_type is None or not isinstance(call, hir.FunctionCall):
        return None
    if name in call.kw_args:
        return call.kw_args[name]
    for index, param in enumerate(function_type.pos_or_kw):
        if param.name == name:
            return call.pos_args[index] if index < len(call.pos_args) else None
    return None


def _object_of(type_: ty.Type) -> ty.ObjectType | None:
    """The object type a value's type denotes, looking through `0 | [...]`."""
    unfolded = ty.unfold(ty.strip_refinement(type_))
    if isinstance(unfolded, ty.TypeOr):
        objects = [item for item in unfolded.items if isinstance(item, ty.ObjectType)]
        unfolded = objects[0] if len(objects) == 1 else None
    return unfolded if isinstance(unfolded, ty.ObjectType) else None


def _member_invariant(node: hir.AST) -> tuple[ty.Proposition, ...]:
    """The invariant declared on the field a member access reads: the
    field's own, plus what enclosing fields declare about it
    (`denominator:bigint<sign =? 1>` speaks about `q.denominator.sign`)."""
    node = _strip_casts(node)
    if not isinstance(node, hir.MemberAccess):
        return ()
    object_type = _object_of(node.value.type)
    field = object_type.field(node.name) if object_type is not None else None
    propositions: list[ty.Proposition] = list(field.refinement) if field is not None else []
    suffix = node.name
    parent = _strip_casts(node.value)
    while isinstance(parent, hir.MemberAccess):
        parent_type = _object_of(parent.value.type)
        parent_field = parent_type.field(parent.name) if parent_type is not None else None
        if parent_field is not None:
            propositions.extend(
                ty.Proposition('length' if p.of == 'length' else 'self', p.op, p.value, term=p.term, term_id=p.term_id)
                for p in parent_field.refinement
                if p.field == suffix
            )
        suffix = f'{parent.name}.{suffix}'
        parent = _strip_casts(parent.value)
    return tuple(propositions)


def _describe_proposition_text(proposition: ty.Proposition) -> str:
    op = proposition.op.replace('not=?', 'not =?')
    if proposition.param is not None:
        return f'{proposition.subject_text} {op} {proposition.bound_text}'
    subject = proposition.field or ('value' if proposition.subject == 'self' else 'length')
    if proposition.field is not None and proposition.of == 'length':
        subject = f'{proposition.field}.length'
    return f'{subject} {op} {proposition.bound_text}'


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
    return Interval(lower, upper, capped=interval.capped)


def _is_length_key(key: int) -> bool:
    return key < 0 and key > -_FACT_BASE


def _known_interval(state: State, key: int, cap: int = _MAX_LENGTH) -> Interval:
    """The interval a key currently has; lengths default to `[0, cap]` (a capped interval)."""
    default = Interval(0, cap, capped=True) if _is_length_key(key) else UNKNOWN_INTERVAL
    return state.get(key, default)


def _conjuncts(condition: hir.AST) -> list[hir.AST]:
    """The operands of a chain of `and`s, left to right (`nand` is not flattened)."""
    if isinstance(condition, hir.ShortCircuit) and condition.op == 'and':
        return [*_conjuncts(condition.left), *_conjuncts(condition.right)]
    return [condition]


def _index_fact_key(index_id: int, array_id: int) -> int:
    return -(_FACT_BASE + (index_id << _FACT_SHIFT) + array_id)


# `x not=? 0` facts are index facts against this pseudo-array: they join,
# widen, and drop on assignment exactly like `i <? xs.length` facts.
_NONZERO_MARK = (1 << _FACT_SHIFT) - 1


def _nonzero_key(binding_id: int) -> int:
    return _index_fact_key(binding_id, _NONZERO_MARK)


def _decode_index_fact(key: int) -> tuple[int, int] | None:
    if key > -_FACT_BASE or key <= -_ORDER_BASE:
        return None
    raw = -key - _FACT_BASE
    return raw >> _FACT_SHIFT, raw & ((1 << _FACT_SHIFT) - 1)


# *Order facts* keep a comparison between two terms — bindings, member routes,
# or lengths, whatever `_binding_id` names — as `larger - smaller >= gap`
# (`i <? xs.length` is gap 1, `start <=? end` gap 0), stored as `[gap, ∞]`.
# They are the one relational fact the analysis holds: `xs.length - i` and
# `end - start` read them. Like index facts they join to the weaker gap, drop
# when either term is assigned, and drop with a sequence's index facts.
_ORDER_BASE = 1 << 42
_ORDER_SHIFT = 21
_LENGTH_TERM = 1 << 20


def _order_term(term: int) -> int:
    """A nonnegative encoding of a `_binding_id` result (length keys are negative)."""
    return term if term >= 0 else _LENGTH_TERM - term


def _order_key(smaller: int, larger: int) -> int:
    return -(_ORDER_BASE + (_order_term(smaller) << _ORDER_SHIFT) + _order_term(larger))


def _decode_order_fact(key: int) -> tuple[int, int] | None:
    """The `(smaller, larger)` terms of an order-fact key, as `_binding_id` names them."""
    if key > -_ORDER_BASE or key <= -_REMAINDER_BASE:
        return None
    raw = -key - _ORDER_BASE
    encoded = raw >> _ORDER_SHIFT, raw & ((1 << _ORDER_SHIFT) - 1)
    return tuple(term if term < _LENGTH_TERM else _LENGTH_TERM - term for term in encoded)  # type: ignore[return-value]


# *Remainder facts* bound a value by what is left of a sequence past an
# offset: `src.length - offset - subject >= gap`, stored as `[gap, ∞]`. They
# come from a call whose result is refined against its parameter's length
# (`eat(src[i..])` with `eat:(src) :> uint64<n => n <=? src.length>` gives
# `length <= src.length - i`), and prove `src[i..i+length)`. Like order facts
# they join to the weaker gap and drop when any of the three terms is
# assigned. The subject may be a binding, a member route, or an element
# route (`matches.*.length`: every element's field).
_REMAINDER_BASE = 1 << 44
_REMAINDER_SHIFT = 21


def _remainder_key(subject: int, sequence_id: int, offset_id: int) -> int:
    return -(_REMAINDER_BASE + (_order_term(subject) << (2 * _REMAINDER_SHIFT)) + (sequence_id << _REMAINDER_SHIFT) + offset_id)


def _decode_remainder_fact(key: int) -> tuple[int, int, int] | None:
    """The `(subject, sequence, offset)` of a remainder-fact key."""
    if key > -_REMAINDER_BASE:
        return None
    raw = -key - _REMAINDER_BASE
    mask = (1 << _REMAINDER_SHIFT) - 1
    subject = raw >> (2 * _REMAINDER_SHIFT)
    return (subject if subject < _LENGTH_TERM else _LENGTH_TERM - subject), (raw >> _REMAINDER_SHIFT) & mask, raw & mask


def _is_runtime_string(type_: ty.Type) -> bool:
    """A string whose grapheme length is only known at runtime."""
    return (isinstance(type_, ty.StringType) and type_.length is None) or type_ == 'string'


def prototype_check_condition(node: hir.AST, kind: str, *, simple, comparison, length_of, integer) -> hir.AST | None:
    """The runtime condition of a `$prototype` check for an unproven site, or
    None when no safe check can be built (the site stays a compile error).
    The callbacks build checker-shaped HIR without importing it here."""
    loc = node.loc

    def conjoin(parts: list[hir.AST]) -> hir.AST:
        condition = parts[0]
        for part in parts[1:]:
            condition = hir.ShortCircuit(loc, 'bool', 'and', condition, part)
        return condition

    if kind == 'index':
        assert isinstance(node, (hir.Index, hir.StringIndex))
        sequence = node.array if isinstance(node, hir.Index) else node.string
        if not (simple(node.index) and isinstance(sequence, hir.ExpressedIdentifier)):
            return None
        length = length_of(sequence)
        if length is None:
            return None
        return conjoin([
            comparison('__le__', integer(0), node.index),
            comparison('__lt__', node.index, length),
        ])
    if kind == 'cast':
        assert isinstance(node, hir.ValueCast)
        if not simple(node.expr):
            return None
        source_layout = ty.fixed_integer_layout(ty.strip_refinement(node.expr.type))
        target_layout = ty.fixed_integer_layout(node.type)
        if source_layout is None or target_layout is None:
            return None
        width, signed = target_layout
        minimum = -(1 << (width - 1)) if signed else 0
        maximum = (1 << (width - (1 if signed else 0))) - 1
        _source_width, source_signed = source_layout
        parts: list[hir.AST] = []
        if not source_signed:
            # an unsigned source: only the maximum can fail, compared unsigned
            if maximum < (1 << 64) - 1:
                parts.append(comparison('__unsigned_lte__', node.expr, integer(maximum)))
        else:
            if minimum > -(1 << 63):
                parts.append(comparison('__le__', integer(minimum), node.expr))
            parts.append(comparison('__le__', node.expr, integer(min(maximum, (1 << 63) - 1))))
        if not parts:
            return None
        return conjoin(parts)
    if kind == 'obligation':
        assert isinstance(node, hir.Obligation)
        if not simple(node.value):
            return None
        parts = []
        for proposition in node.refined.propositions:
            if proposition.field is not None:
                return None
            name = {'=?': '__eq__', 'not=?': '__ne__', '<?': '__lt__', '<=?': '__le__', '>?': '__gt__', '>=?': '__ge__'}.get(proposition.op)
            if name is None or proposition.term is not None:
                return None
            if proposition.subject == 'length':
                subject = length_of(node.value)
                if subject is None:
                    return None
            else:
                subject = node.value
            parts.append(comparison(name, subject, integer(proposition.value)))
        if not parts:
            return None
        return conjoin(parts)
    return None


def predicate_bounds_counter(condition: hir.AST, target_id: int) -> bool:
    """Whether a loop guard's predicates strictly bound the target above by a
    value no wider than a signed word (`i <? n`, `n >? i`, possibly among
    `and`-joined predicates): then a `0..` counter never passes `int64.max`."""

    def word_bound(operand: hir.AST) -> bool:
        if isinstance(operand.type, ty.IntegerLiteralType):
            return ty.integer_literal_fits(operand.type.value, 'int64')   # a constant length or limit
        layout = ty.fixed_integer_layout(operand.type)
        if layout is None:
            return False
        width, signed = layout
        return width < 64 or (width == 64 and signed)

    def is_target(operand: hir.AST) -> bool:
        operand = _strip_casts(operand)
        return isinstance(operand, hir.ExpressedIdentifier) and operand.binding_id == target_id

    if isinstance(condition, hir.ShortCircuit) and condition.op == 'and':
        return predicate_bounds_counter(condition.left, target_id) or predicate_bounds_counter(condition.right, target_id)
    def below_word_max(operand: hir.AST) -> bool:
        """An inclusive bound the counter may reach and step past without leaving the
        word: a length (capped by the address space) or a sub-word-range value."""
        stripped = _strip_casts(operand)
        if isinstance(stripped, (hir.ArrayLength, hir.StringLength)):
            return True
        if isinstance(operand.type, ty.IntegerLiteralType):
            return operand.type.value < (1 << 63) - 1
        layout = ty.fixed_integer_layout(ty.strip_refinement(operand.type))
        if layout is None:
            return False
        width, signed = layout
        return (width < 64) if signed else (width < 63)

    if (
        isinstance(condition, hir.FunctionCall)
        and isinstance(condition.func, hir.ExpressedIdentifier)
        and len(condition.pos_args) == 2
    ):
        left, right = condition.pos_args
        if condition.func.name == '__lt__':
            return is_target(left) and word_bound(right)
        if condition.func.name == '__gt__':
            return is_target(right) and word_bound(left)
        if condition.func.name == '__le__':
            return is_target(left) and below_word_max(right)
        if condition.func.name == '__ge__':
            return is_target(right) and below_word_max(left)
    return False


def _strip_casts(node: hir.AST) -> hir.AST:
    """Through value/representation casts and obligation wrappers to the value itself."""
    while isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Obligation)):
        node = node.expr if not isinstance(node, hir.Obligation) else node.value
    return node


def _sequence_of(node: hir.AST) -> hir.AST | None:
    """The sequence a `.length` node measures (arrays and strings alike), through
    the cast a comparison with a fixed width wraps it in (`i:uint64 <? xs.length`)."""
    node = _strip_casts(node)
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
        remainder = _decode_remainder_fact(key)
        if remainder is not None:
            subject, sequence, offset = remainder
            if (index_id is not None and index_id in (subject, offset)) or (array_id is not None and array_id == sequence):
                del state[key]
            continue
        order = _decode_order_fact(key)
        if order is not None:
            # an order fact mentioning the assigned term, or the sequence's length
            terms = [index_id, None if array_id is None else _length_key(array_id)]
            if any(term is not None and term in order for term in terms):
                del state[key]
            continue
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
        target: str = 'x86_64',
    ) -> None:
        self.registry = registry
        self.target = target
        self.max_length = max_length(target)
        self.cap_notes: list[CapNote] = []
        self.prototype_sites: dict[int, tuple[str, Error]] | None = None
        # bindings declared with a refinement (`let d:bigint<sign =? 1>`, refined
        # parameters): their facts are re-established after every assignment
        self.declared_refinements: dict[int, ty.RefinedType] = {}
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
            if node.binding_id is not None and self._nonzero_proven(node.expr, interval, current):
                # `let d = -denominator`, `let g = gcd(…)`: the initializer's nonzero-ness is a fact on the binding
                current[_nonzero_key(node.binding_id)] = Interval.exact(1)
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
                self._seed_value_facts(node.binding_id, node.expr, current, node.loc)
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
            shifted = self._shifted_facts(current, binding_id, node) if node.op in ('+=', '-=') else {}
            _drop_index_facts(current, index_id=binding_id)
            current.update(shifted)   # `i += 2` under `src.length - i >= 2`: `i <= src.length`
            if (isinstance(node.target.type, ty.ArrayType) and node.target.type.length is None) or _is_runtime_string(node.target.type):
                # Whole-sequence replacement: nothing is known about the new length.
                current.pop(_length_key(binding_id), None)
                _drop_index_facts(current, array_id=binding_id)
                known = self._string_length(_strip_casts(node.value).type) if _is_runtime_string(node.target.type) else None
                if known is not None:
                    current[_length_key(binding_id)] = Interval.exact(known)
            self._drop_route_facts(current, binding_id)
            if node.op == '=':
                self._seed_value_facts(binding_id, node.value, current, node.loc)
            declared = self.declared_refinements.get(binding_id)
            if declared is not None:
                # `result = f(…)` on `result:bigint<sign =? 1>`: the assigned value
                # was checked against the refinement, so its facts hold again
                for proposition in declared.propositions:
                    if proposition.field is not None:
                        self._seed_field_proposition(binding_id, proposition, declared.base, current, node.loc)
                    elif proposition.subject == 'self':
                        bounded = Interval(proposition.lower_bound(), proposition.upper_bound())
                        existing = current.get(binding_id)
                        current[binding_id] = bounded if existing is None else existing.intersect(bounded)
                        if proposition.op == 'not=?' and proposition.value == 0:
                            current[_nonzero_key(binding_id)] = Interval.exact(1)
                    elif proposition.subject == 'length':
                        minimum = proposition.lower_bound()
                        if minimum is not None:
                            key = _length_key(binding_id)
                            current[key] = current.get(key, self._length_default()).intersect(Interval(minimum, self.max_length))
            return current
        if isinstance(node, hir.IndexAssign):
            self._eval(node.target, current, validate=validate)
            self._eval(node.value, current, validate=validate)
            target = _strip_casts(node.target)
            if isinstance(target, hir.Index):
                stored_into = _runtime_array_id(target.array, self.registry)
                if stored_into is not None:
                    self._store_element(current, stored_into, node.value, node.loc)
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
        """The interval excludes zero, a `not=? 0` guard covers the binding, or a declared invariant does."""
        if interval is not None and (
            (interval.lower is not None and interval.lower > 0)
            or (interval.upper is not None and interval.upper < 0)
        ):
            return True
        binding = self._binding_id(node)
        if binding is not None and _nonzero_key(binding) in state:
            return True
        if _excludes_zero(_member_invariant(node)):
            return True
        refined_result = _call_result_refinement(node)
        if refined_result is not None and _excludes_zero(refined_result.propositions):
            return True
        stripped = _strip_casts(node)
        if (
            isinstance(stripped, hir.FunctionCall)
            and isinstance(stripped.func, hir.ExpressedIdentifier)
            and stripped.func.name == '__unary_sub__'
            and len(stripped.pos_args) == 1
        ):
            # negation keeps a value nonzero (even at the wrapping minimum)
            return self._nonzero_proven(stripped.pos_args[0], self._eval(stripped.pos_args[0], state, validate=False), state)
        return False

    def _tightened(self, node: hir.AST, interval: Interval | None, state: State) -> Interval | None:
        """An interval whose bound sits on zero moves past it when the value is known nonzero."""
        if interval is None:
            return None
        if interval.lower == 0 or interval.upper == 0:
            if self._nonzero_proven(node, None, state):
                lower = 1 if interval.lower == 0 else interval.lower
                upper = -1 if interval.upper == 0 else interval.upper
                return Interval(lower, upper)
        return interval

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
            if proposition.when is not None:
                # a fact of one arm of a boolean result: it must hold wherever the
                # returned expression is that arm — vacuously when it cannot be
                arm_state = self._refine(state, _strip_casts(node.value), truth=proposition.when)
                if arm_state is None:
                    continue
                verdict = self._proposition_verdict(proposition, node.value, interval, arm_state)
                if verdict is True:
                    continue
                self._proof_failure(node, 'obligation', Error(
                    srcfile=self.srcfile,
                    title='refinement refuted' if verdict is False else 'cannot prove fact',
                    pointer_messages=[Pointer(span=node.value.loc, message=f'`{_describe_proposition_text(proposition)}` is promised when this is `{str(proposition.when).lower()}`, and nothing here establishes it')],
                    hint='return under a guard that establishes the fact (`if prefix.length >? src.length return false` before `return true`)',
                ))
                return
            verdict = self._proposition_verdict(proposition, node.value, interval, state)
            if verdict is True:
                if proposition.op in ('<?', '<=?') and (proposition.subject == 'length' or proposition.of == 'length'):
                    _node, subject = self._subject_interval(proposition, node.value, interval, state)
                    name = {'<?': '__lt__', '<=?': '__le__'}[proposition.op]
                    if subject is not None and subject.capped and self._decide_comparison(name, Interval(subject.lower, None), Interval.exact(proposition.value)) is not True:
                        self._cap_note(node.value, f'`{_describe_proposition_text(proposition)}` holds')
                continue
            requirement = _describe_proposition_text(proposition)
            source = ' '.join(self.srcfile.body[node.value.loc.start:node.value.loc.stop].split())
            if proposition.field is not None:
                source = f'{source}.{proposition.field}'
            _node, subject_interval = self._subject_interval(proposition, node.value, interval, state)
            self._proof_failure(node, 'obligation', Error(
                srcfile=self.srcfile,
                title='refinement refuted' if verdict is False else 'cannot prove refinement',
                pointer_messages=[Pointer(
                    span=node.value.loc,
                    message=f'`{requirement}` is required here' if verdict is False else f'no fact establishes `{requirement}` (neither proven nor refuted)',
                )],
                notes=[f'`{source}` {self._describe_interval(subject_interval, array=proposition.subject == "length")}'],
                hint=None if verdict is False else 'establish it with a guard (`if … { }`), or check it with `$runtime_assert`',
            ))
            return

    def _length_interval(self, node: hir.AST, state: State) -> Interval | None:
        known = self._string_length(_strip_casts(node).type) if not isinstance(node.type, ty.ArrayType) else node.type.length   # a literal keeps its length through the cast to `string`
        if known is not None:
            return Interval.exact(known)
        if isinstance(_strip_casts(node), hir.StringSlice):
            return self._slice_length_interval(_strip_casts(node), state)
        sequence_id = _runtime_array_id(node, self.registry)
        if sequence_id is None:
            return None
        interval = state.get(_length_key(sequence_id), self._length_default())
        # `limbs:array<uint64 length >? 0>`: the field's declared length bound is a fact on every read
        declared = _length_propositions_interval(_member_invariant(node))
        return interval if declared is None else interval.intersect(declared)

    def _slice_length_interval(self, node: hir.StringSlice, state: State) -> Interval | None:
        """The length of `s[a..b]`: its exclusive end minus its start, read with
        the order facts (`s[i..]` under `i <? s.length` is at least 1) and
        never negative (the slice's own validation proved its endpoints)."""
        loc = node.loc
        bounds = node.range.bounds or '[]'
        string_id = _runtime_array_id(node.string, self.registry)
        start_node: hir.AST = node.range.left if node.range.left is not None else hir.Integer(loc, ty.IntegerLiteralType(0), '0d', 0)
        start_delta = 1 if bounds[0] == '(' else 0
        length_node = hir.StringLength(loc, 'int64', node.string)
        end_delta = 0
        end_node: hir.AST
        offset = self._length_offset_index(node.range.right, string_id) if node.range.right is not None and string_id is not None else None
        if node.range.right is None:
            end_node = length_node                                   # `s[i..]`: to the end
        elif offset is not None:
            end_node = length_node                                   # `s[i..end]`, `s[i..end - 1]`: the length less k
            end_delta = -offset + (1 if bounds[1] == ']' else 0)
        else:
            end_node = node.range.right
            end_delta = 1 if bounds[1] == ']' else 0
        end_interval = self._eval(end_node, state, validate=False)
        start_interval = self._eval(start_node, state, validate=False)
        difference = hir.FunctionCall(loc, 'int64', hir.ExpressedIdentifier(loc, 'int64', '__sub__'), [end_node, start_node], {})
        result = self._binary_interval('__sub__', end_interval, start_interval, 'int64', bound=self._difference_bound(difference, state))
        if result is None:
            return None
        shift = end_delta - start_delta
        result = Interval(_add(result.lower, shift), _add(result.upper, shift), capped=result.capped)
        return result.intersect(Interval(0, None))

    def _field_node(self, value: hir.AST, field: str) -> hir.AST:
        """`value.field` (a path) as a node: the literal's field, or a member access (tracked by route)."""
        node = value
        for part in field.split('.'):
            literal = _strip_casts(node)
            found = None
            if isinstance(literal, hir.ObjectLiteral):
                found = next((item.value for item in literal.fields if item.name == part), None)
            if found is not None:
                node = found
                continue
            object_type = _object_of(literal.type)
            declared = object_type.field(part) if object_type is not None else None
            node = hir.MemberAccess(value.loc, declared.type if declared is not None else 'int64', literal, part, True)
        return node

    def _subject_interval(self, proposition: ty.Proposition, value: hir.AST, interval: Interval | None, state: State) -> tuple[hir.AST, Interval | None]:
        """The node and interval a proposition's subject denotes for ``value``."""
        if (field := proposition.field) is not None:
            node = self._field_node(value, field)
            if proposition.of == 'length':
                return node, self._length_interval(node, state)
            return node, self._eval(node, state, validate=False)
        if proposition.subject == 'self':
            return value, interval
        return value, self._length_interval(value, state)

    def _proposition_verdict(self, proposition: ty.Proposition, value: hir.AST, interval: Interval | None, state: State) -> bool | None:
        """True when the facts prove the proposition, False when they refute it, None otherwise."""
        if proposition.param is not None:
            # a fact about a parameter (`prefix.length <=? src.length`): its own facts decide it
            if proposition.subject_id is None:
                return None
            subject = _length_key(proposition.subject_id) if proposition.of == 'length' else proposition.subject_id
            if proposition.term is not None:
                if proposition.term_id is None:
                    return None
                gap = 1 if proposition.op == '<?' else 0
                return True if self._id_bounded_by_length(subject, proposition.term_id, gap, state) else None
            subject_interval = _known_interval(state, subject, self.max_length) if proposition.of == 'length' else self._binding_interval(state, subject)
            name = {'>?': '__gt__', '>=?': '__ge__', '<?': '__lt__', '<=?': '__le__', '=?': '__eq__', 'not=?': '__ne__'}.get(proposition.op)
            return self._decide_comparison(name, subject_interval, Interval.exact(proposition.value)) if name is not None else None
        if proposition.term is not None:
            # `n <=? src.length`: the subject is bounded by that parameter's length
            if proposition.term_id is None:
                return None
            subject_node, _interval = self._subject_interval(proposition, value, interval, state)
            gap = 1 if proposition.op == '<?' else 0
            return True if self._bounded_by_length(subject_node, proposition.term_id, gap, state) else None
        refined_result = _call_result_refinement(value)
        if refined_result is not None and proposition in refined_result.propositions:
            return True   # `f():>bigint<sign =? 1>` proves `sign =? 1` of its result
        stripped = _strip_casts(value)
        if isinstance(stripped, hir.ExpressedIdentifier) and stripped.binding_id is not None and stripped.binding_id not in self.assigned:
            # `_BIGINT_ONE:bigint<sign =? 1> = […]`: a never-reassigned binding's
            # declared refinement holds wherever it is read (facts seeded at
            # its declaration do not reach other function bodies)
            binding = self.registry.by_id.get(stripped.binding_id)
            declaration = binding.declaration if binding is not None else None
            if (
                declaration is not None
                and isinstance(declaration.annotation, ty.RefinedType)
                and proposition in declaration.annotation.propositions
            ):
                return True
        subject_node, subject = self._subject_interval(proposition, value, interval, state)
        subject = self._tightened(subject_node, subject, state)
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

    def _seed_field_proposition(self, root_id: int, proposition: ty.Proposition, base: ty.Type, state: State, loc: Span) -> None:
        """A field-subject proposition (`.sign =? 1`, `.denominator.sign =? 1`) as facts on the member route."""
        assert proposition.field is not None
        path = tuple(proposition.field.split('.'))
        current: ty.Type = base
        leaf: ty.Type = 'int64'
        for part in path:
            object_type = _object_of(current)
            declared = object_type.field(part) if object_type is not None else None
            leaf = declared.type if declared is not None else 'int64'
            current = leaf
        route_id = self.registry.route_id(root_id, path, leaf, loc)
        if proposition.of == 'length':
            minimum = proposition.lower_bound()
            if minimum is not None:
                key = _length_key(route_id)
                state[key] = state.get(key, self._length_default()).intersect(Interval(minimum, self.max_length))
            return
        lower, upper = proposition.lower_bound(), proposition.upper_bound()
        if lower is not None or upper is not None:
            current_interval = state.get(route_id, UNKNOWN_INTERVAL)
            state[route_id] = current_interval.intersect(Interval(lower, upper))
        if proposition.op == 'not=?' and proposition.value == 0:
            state[_nonzero_key(route_id)] = Interval.exact(1)

    def _seed_parameter_refinements(self, function: hir.FunctionLiteral, state: State) -> None:
        """Inside the body a refined parameter's propositions are facts."""
        param_loc = function.loc
        for param in [*function.pos_or_kw_args, *function.kw_only_args]:
            if not isinstance(param.type, ty.RefinedType) or param.binding_id is None:
                continue
            self.declared_refinements[param.binding_id] = param.type
            lower: int | None = None
            upper: int | None = None
            for proposition in param.type.propositions:
                if proposition.field is not None:
                    # `r:Ratio<bottom >? 0>`: a fact on the field's member route
                    self._seed_field_proposition(param.binding_id, proposition, param.type.base, state, param_loc)
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
                        state[key] = state.get(key, self._length_default()).intersect(Interval(minimum, self.max_length))
            if lower is not None or upper is not None:
                self._set_interval(state, param.binding_id, Interval(lower, upper))

    def _validate_assert(self, node: hir.Assert, state: State) -> None:
        """`$assert` is proven when its false path is impossible, refuted when its true path is."""
        if self._refine(state, node.condition, truth=False) is None:
            return
        refuted = self._refine(state, node.condition, truth=True) is None
        if node.runtime and not refuted:
            return
        if node.expect:
            # a refuted expectation is a test failure, not a compile error: the
            # test still builds and reports it when it runs
            user_warning(
                self.srcfile,
                'expectation refuted at compile time',
                Pointer(span=node.condition.loc, message=node.message or 'this condition is false for every value the analysis admits'),
                hint='the test will fail when it runs',
            )
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

        # Narrowing: widening over-approximates (`i += 1` sends `i` to [0, ∞]),
        # so re-run the body from the widened head with the guard applied and
        # keep what comes back — under `loop i <? xs.length` that is [0, cap].
        # A decreasing iteration from a post-fixpoint stays sound.
        for _ in range(3):
            true_state = self._refine(head, condition, truth=True)
            if true_state is None:
                break
            transfer = self._loop_transfer(body, true_state, validate=False)
            backedges = [
                *([transfer.normal] if transfer.normal is not None else []),
                *transfer.continues.get(0, []),
            ]
            narrowed = self._narrow_states(head, self._join_states([state, *backedges]))
            if narrowed == head:
                break
            head = narrowed

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

        iterated = _runtime_array_id(iterator.iterable, self.registry) if isinstance(iterator.iterable.type, ty.ArrayType) else None

        def enter(head: State) -> State:
            body_state = dict(head)
            if iterator.target.binding_id is not None:
                body_state[iterator.target.binding_id] = self._loop_counter_interval(iterator)
                if iterated is not None:
                    self._read_element(body_state, iterated, iterator.target.binding_id, iterator.loc)
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
                    body_state[iterator.target.binding_id] = self._loop_counter_interval(iterator)
            return body_state

        return self._iterate_loop(body, state, enter, target_ids, validate=validate)

    def _binding_interval(self, state: State, binding_id: int) -> Interval:
        """A binding's interval: its tracked facts, else its fixed width's range, else unknown."""
        known = state.get(binding_id)
        if known is not None:
            return known
        if _is_length_key(binding_id):
            return _known_interval(state, binding_id, self.max_length)   # lengths default to `[0, cap]`
        declared = self._type_interval(binding_id)
        return UNKNOWN_INTERVAL if declared is None else declared

    def _type_interval(self, binding_id: int) -> Interval | None:
        """The range of a binding's fixed width (`[0, 2^64-1]` for a `uint64`), if it has one."""
        binding = self.registry.by_id.get(binding_id)
        if binding is None:
            return None
        # `let i:uint64 = 0` records the initializer's type (`0`) on the binding; the annotation is the width
        declared = binding.declaration.annotation if isinstance(binding.declaration, hir.Declare) and binding.declaration.annotation is not None else binding.type
        layout = ty.fixed_integer_layout(ty.strip_refinement(declared)) if declared is not None else None
        if layout is None and isinstance(declared, ty.TypeOr):
            # `uint64 | none`: read as a number, the value is the one fixed-width member
            layouts = {ty.fixed_integer_layout(ty.strip_refinement(item)) for item in declared.items} - {None}
            layout = layouts.pop() if len(layouts) == 1 else None
        if layout is None:
            return None
        width, signed = layout
        return Interval(-(1 << (width - 1)), (1 << (width - 1)) - 1) if signed else Interval(0, (1 << width) - 1)

    def _proof_failure(self, node: hir.AST, kind: str, report: Error) -> None:
        """An unproven obligation: a compile error, or in `$prototype` a
        recorded site that becomes a runtime check panicking with this report."""
        if self.prototype_sites is not None:
            self.prototype_sites[id(node)] = (kind, report)
            return
        raise UserError(report)

    def _length_default(self) -> Interval:
        """An unknown length: `[0, cap]` by the address-space axiom (a capped interval)."""
        return Interval(0, self.max_length, capped=True)

    def _cap_note(self, node: hir.AST, what: str) -> None:
        bits = ADDRESS_BITS[self.target]   # type: ignore[index]
        self.cap_notes.append(CapNote(self.srcfile, node.loc, f'{what} only because lengths are assumed below 2^{bits} on `{self.target}`'))

    def _loop_counter_interval(self, iterator: hir.IteratorExpression) -> Interval:
        """The iterator's interval inside its loop. A right-unbounded counter
        (`i in 0..`) whose loop guard bounds it (`i <? E` for a word-sized `E`,
        see `predicate_bounds_counter`) never passes `E <= int64.max`: the guard
        breaks the loop at the first `i >= E`."""
        if iterator.guarded and iterator.step > 0:
            upper = (1 << 63) - 1
            return Interval(iterator.first, upper if iterator.last is None else min(upper, iterator.last))
        return self._iterator_interval(iterator)

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
                # a `not=? 0` fact moves a bound that sits on zero past it
                if node.binding_id is not None and _nonzero_key(node.binding_id) in state and (interval.lower == 0 or interval.upper == 0):
                    return Interval(1 if interval.lower == 0 else interval.lower, -1 if interval.upper == 0 else interval.upper)
                return interval
            constant = self._constant_binding(node.binding_id, set())
            if constant is not None:
                return constant
            layout = ty.fixed_integer_layout(ty.strip_refinement(node.type))
            if layout is not None:
                # a fixed-width value with no tracked facts lies in its type's range
                width, signed = layout
                return Interval(-(1 << (width - 1)), (1 << (width - 1)) - 1) if signed else Interval(0, (1 << width) - 1)
            return None
        if isinstance(node, hir.Place):
            self._eval(node.target, state, validate=validate)
            root = node.target
            while isinstance(root, (hir.MemberAccess, hir.Index)):
                root = root.value if isinstance(root, hir.MemberAccess) else root.array
            if isinstance(root, hir.ExpressedIdentifier) and root.binding_id is not None:
                state.pop(root.binding_id, None)
                self._drop_route_facts(state, root.binding_id)   # the callee may store anything
            return None
        if isinstance(node, hir.ValueCast):
            inner = self._eval(node.expr, state, validate=validate)
            if inner is None:
                # any fixed-width-typed expression lies in its type's range
                source_layout = ty.fixed_integer_layout(ty.strip_refinement(node.expr.type))
                if source_layout is not None:
                    width, signed = source_layout
                    inner = Interval(-(1 << (width - 1)), (1 << (width - 1)) - 1) if signed else Interval(0, (1 << width) - 1)
            fitted = self._fit_type(inner, node.type)
            if validate and fitted is not None and inner is not None and inner.capped and self._fit_type(Interval(inner.lower, None), node.type) is None:
                self._cap_note(node, f'fits `{type_to_dewy(node.type)}`')
            if (
                validate
                and fitted is None
                and self.prototype_sites is not None
                and ty.fixed_integer_layout(ty.strip_refinement(node.expr.type)) is not None
                and ty.fixed_integer_layout(node.type) is not None
            ):
                # `$prototype`: a fixed-width narrowing becomes a runtime range check
                self._proof_failure(node, 'cast', Error(
                    srcfile=self.srcfile,
                    title=f'cannot prove this integer fits `{node.type}`',
                    pointer_messages=[Pointer(span=node.loc, message=f'the value is a `{ty.strip_refinement(node.expr.type)}`, whose range is not proven inside `{node.type}`')],
                    hint='narrow the value with a comparison to prove it',
                ))
                return fitted
            if (
                validate
                and fitted is None
                and (node.expr.type in ('int', 'uint') or ty.fixed_integer_layout(ty.strip_refinement(node.expr.type)) is not None)
                and ty.fixed_integer_layout(node.type) is not None
            ):
                # Narrowing an arbitrary-precision integer — or another fixed
                # width — to a fixed width is only allowed when the analysis
                # proves the value fits.
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
                    return state.get(_length_key(array_id), self._length_default())
                return self._length_default()
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
                return state.get(_length_key(string_id), self._length_default())
            return self._length_default()
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
                current = state.get(key, self._length_default())
                if validate and index_arg is not None and name in {'pop', 'insert'}:
                    self._validate_method_index(
                        node, index_arg, index_interval, state, array_id, current,
                        allow_end=name == 'insert',
                    )
                if name in {'push', 'insert'}:
                    stored = node.pos_args[0] if node.pos_args else node.kw_args.get('value')
                    if stored is not None:
                        self._store_element(state, array_id, stored, node.loc)
                    state[key] = Interval(
                        _add(current.lower, 1),
                        _minimum_upper(_add(current.upper, 1), self.max_length),
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
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ExpressedIdentifier) and node.func.name.startswith(('_capture_push', '_capture_add')) and len(node.pos_args) == 2 and isinstance(node.pos_args[0], hir.Place):
            # `[loop … value]`: the capture's push — the element's facts join the array's
            self._eval(node.pos_args[1], state, validate=validate)
            target = _strip_casts(node.pos_args[0].target)
            capture_id = _runtime_array_id(target, self.registry)
            if capture_id is not None:
                self._store_element(state, capture_id, node.pos_args[1], node.loc)
                length = state.get(_length_key(capture_id), self._length_default())
                state[_length_key(capture_id)] = Interval(_add(length.lower, 1), _minimum_upper(_add(length.upper, 1), self.max_length))
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
            if _call_result_refinements(node):
                self._apply_call_facts(state, node, None)   # what the result promises of the arguments unconditionally
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
                    bound=self._difference_bound(node, state) if name == '__sub__' else None,
                )
            refined_result = _call_result_refinement(node)
            if refined_result is not None:
                declared = _propositions_interval(refined_result.propositions)
                if declared is not None:
                    result = declared if result is None else result.intersect(declared)
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
            interval = state.get(route_id) if route_id is not None else None
            declared = _propositions_interval(_member_invariant(node))
            if declared is not None:
                interval = declared if interval is None else interval.intersect(declared)
            return interval
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

    def _difference_bound(self, node: hir.FunctionCall, state: State) -> Interval | None:
        """What the order facts say about `left - right`: `xs.length - i` is at
        least 1 under `i <? xs.length`, `end - start` at least 0 under
        `start <=? end` (and at most `-gap` when the facts run the other way)."""
        left_id, right_id = self._binding_id(node.pos_args[0]), self._binding_id(node.pos_args[1])
        if left_id is None or right_id is None or left_id == right_id:
            return None
        lower = state.get(_order_key(right_id, left_id))   # right <= left - gap
        upper = state.get(_order_key(left_id, right_id))   # left <= right - gap
        bound = Interval(
            None if lower is None else lower.lower,
            None if upper is None or upper.lower is None else -upper.lower,
        )
        return None if bound == UNKNOWN_INTERVAL else bound

    def _binary_interval(
        self,
        name: str,
        left: Interval | None,
        right: Interval | None,
        result_type: ty.Type,
        *,
        bound: Interval | None = None,
    ) -> Interval | None:
        if bound is not None and (left is None or right is None):
            # the operands alone say nothing, the order fact still does
            return self._fit_type(bound, result_type)
        result = self._binary_interval_plain(name, left, right, result_type, bound=bound)
        if result is not None and left is not None and right is not None and (left.capped or right.capped) and not result.capped:
            result = Interval(result.lower, result.upper, capped=True)
        return result

    def _binary_interval_plain(
        self,
        name: str,
        left: Interval | None,
        right: Interval | None,
        result_type: ty.Type,
        *,
        bound: Interval | None = None,
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
        if bound is not None:
            # a relational fact narrows the mathematical result before the
            # width check: `xs.length - i` proven positive cannot roll over
            result = result.intersect(bound)
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

    # ---- facts that bound a value by a sequence's length ----

    def _bounded_by_length(self, node: hir.AST, sequence_id: int, gap: int, state: State) -> bool:
        """Whether `sequence.length - node >= gap` is established: by an order or
        index fact on a binding (`i <? src.length`), by the node being the
        length itself less a constant, by a binding plus a constant, by a sum
        `i + length` with a remainder fact, by an interval under the proven
        minimum length, or by a call whose result is refined against the
        parameter this sequence (or a tail of it) was passed for."""
        node = _strip_casts(node)
        if isinstance(node, hir.Transmute):
            # `i transmute uint64`: the same number when the source is not negative
            inner = self._eval(node.expr, state, validate=False)
            if inner is not None and inner.lower is not None and inner.lower >= 0:
                return self._bounded_by_length(node.expr, sequence_id, gap, state)
            return False
        subject = self._binding_id(node)
        if subject is None:
            subject = self._element_route_of(node)
        if subject is not None and self._id_bounded_by_length(subject, sequence_id, gap, state):
            return True
        offset = self._length_offset_index(node, sequence_id)
        if offset is not None and offset >= gap:
            return True
        minimum = state.get(_length_key(sequence_id), self._length_default()).lower or 0
        interval = self._eval(node, state, validate=False)
        if interval is not None and interval.upper is not None and interval.upper <= minimum - gap:
            return True
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ExpressedIdentifier) and node.func.name == '__sub__' and len(node.pos_args) == 2:
            # `n - c`: bounded when `n` is, by `c` less
            constant = self._constant_expr(node.pos_args[1], set())
            if constant is not None and constant.lower is not None and constant.lower == constant.upper and constant.lower >= 0:
                return self._bounded_by_length(node.pos_args[0], sequence_id, gap - constant.lower, state)
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ExpressedIdentifier) and node.func.name == '__add__' and len(node.pos_args) == 2:
            left, right = node.pos_args
            for value, other in ((left, right), (right, left)):
                constant = self._constant_expr(other, set())
                if constant is not None and constant.lower is not None and constant.lower == constant.upper and constant.lower >= 0:
                    return self._bounded_by_length(value, sequence_id, gap + constant.lower, state)
            left_id, right_id = self._binding_id(left), self._binding_id(right)
            if left_id is not None and right_id is not None and left_id >= 0 and right_id >= 0:
                for subject_id, offset_id in ((left_id, right_id), (right_id, left_id)):
                    remainder = state.get(_remainder_key(subject_id, sequence_id, offset_id))
                    if remainder is not None and remainder.lower is not None and remainder.lower >= gap:
                        return True
        for fact in self._call_term_facts(node):
            fact_sequence, fact_offset, fact_gap = fact
            if fact_sequence == sequence_id and fact_gap >= gap and (fact_offset is None or self._nonnegative(fact_offset, state)):
                return True
        return False

    def _id_bounded_by_length(self, subject: int, sequence_id: int, gap: int, state: State) -> bool:
        """`sequence.length - subject >= gap` for a term the facts name: a binding,
        a route, or a length key (`prefix.length <=? src.length`)."""
        if subject == _length_key(sequence_id):
            return gap <= 0   # the length itself
        order = state.get(_order_key(subject, _length_key(sequence_id)))
        if order is not None and order.lower is not None and order.lower >= gap:
            return True
        if subject >= 0 and gap <= 1 and _index_fact_key(subject, sequence_id) in state:
            return True
        if subject < 0:
            # a length: under the sequence's proven minimum
            known = _known_interval(state, subject, self.max_length)
            minimum = state.get(_length_key(sequence_id), self._length_default()).lower or 0
            if known.upper is not None and known.upper <= minimum - gap:
                return True
        for key, interval in state.items():
            remainder = _decode_remainder_fact(key)
            if remainder is not None and remainder[0] == subject and remainder[1] == sequence_id and interval.lower is not None and interval.lower >= gap:
                return True   # `length <= src.length - i` bounds `length` by `src.length` too (`i >= 0`)
        return False

    def _nonnegative(self, binding_id: int, state: State) -> bool:
        interval = self._binding_interval(state, binding_id)
        return interval.lower is not None and interval.lower >= 0

    def _call_term_facts(self, node: hir.AST) -> list[tuple[int, int | None, int]]:
        """What a call's refined result promises about a sequence it was passed:
        `(sequence id, offset binding or None, gap)` per length term — the
        result is at most `sequence.length - offset - gap` (`offset` when the
        argument was a tail `src[i..]`, None when the sequence itself)."""
        facts: list[tuple[int, int | None, int]] = []
        for refined in _call_result_refinements(node):
            for proposition in refined.propositions:
                if proposition.term is None or proposition.subject != 'self':
                    continue
                gap = 1 if proposition.op == '<?' else 0
                argument = _call_argument(node, proposition.term)
                if argument is None:
                    continue
                argument = _strip_casts(argument)
                sequence_id = _runtime_array_id(argument, self.registry)
                if sequence_id is not None:
                    facts.append((sequence_id, None, gap))
                    continue
                tail = self._tail_of(argument)
                if tail is not None:
                    facts.append((tail[0], tail[1], gap))
        return facts

    def _tail_of(self, node: hir.AST) -> tuple[int, int] | None:
        """`src[i..]`, `src[i..end]`, `src[i..src.length)`: the sequence and the
        offset binding of a slice running to the end, if that is what it is."""
        node = _strip_casts(node)
        if not isinstance(node, hir.StringSlice) or node.range.left is None:
            return None
        bounds = node.range.bounds or '[]'
        if bounds[0] != '[':
            return None
        sequence_id = _runtime_array_id(node.string, self.registry)
        offset_id = self._binding_id(node.range.left)
        if sequence_id is None or offset_id is None or offset_id < 0:
            return None
        right = node.range.right
        to_the_end = (
            right is None
            or (bounds[1] == ']' and self._length_offset_index(right, sequence_id) == 1)
            or (bounds[1] == ')' and _sequence_of(right) is not None and _runtime_array_id(_sequence_of(right), self.registry) == sequence_id)   # type: ignore[arg-type]
        )
        return (sequence_id, offset_id) if to_the_end else None

    def _seed_call_term_facts(self, subject: int, value: hir.AST, state: State) -> None:
        """`let length = eat(src[i..])`: the call's promise as facts on the binding."""
        for refined in _call_result_refinements(value):
            for proposition in refined.propositions:
                if proposition.term is None or proposition.subject != 'self':
                    continue
                argument = _call_argument(value, proposition.term)
                known = self._length_interval(argument, state) if argument is not None else None
                if known is not None and known.upper is not None:
                    # a sequence of known length: the promise is a plain bound
                    bound = Interval(None, known.upper - (1 if proposition.op == '<?' else 0))
                    state[subject] = self._binding_interval(state, subject).intersect(bound)
        for sequence_id, offset_id, gap in self._call_term_facts(value):
            if offset_id is None:
                state[_order_key(subject, _length_key(sequence_id))] = Interval(gap, None)
            elif self._nonnegative(offset_id, state):
                state[_remainder_key(subject, sequence_id, offset_id)] = Interval(gap, None)
                state[_order_key(subject, _length_key(sequence_id))] = Interval(gap, None)

    def _seed_value_facts(self, subject: int, value: hir.AST, state: State, loc: Span) -> None:
        """What a stored value says about its new binding: a refined call's
        promise, a sum's bound, another binding's (or element's) facts."""
        self._seed_call_term_facts(subject, value, state)
        self._seed_sum_facts(subject, value, state)
        stripped = _strip_casts(value)
        source = self._binding_id(stripped) if isinstance(stripped, (hir.ExpressedIdentifier, hir.MemberAccess)) else None
        if source is not None and source >= 0:
            self._copy_relational_facts(state, source, subject)
            if isinstance(stripped, hir.ExpressedIdentifier):
                self._copy_element_facts(state, source, subject, loc)
                for route in self.registry.routes_under(source):
                    path = self.registry.route_paths[route]
                    if path and path[0] != '*':
                        self._copy_relational_facts(state, route, self.registry.route_id(subject, path, 'int64', loc))
            return
        element = self._element_route_of(stripped)
        if element is not None:
            self._copy_relational_facts(state, element, subject)
            if isinstance(stripped, hir.Index):
                read_from = _runtime_array_id(stripped.array, self.registry)
                if read_from is not None:
                    self._read_element(state, read_from, subject, loc)
            return
        if isinstance(stripped, hir.Index):
            read_from = _runtime_array_id(stripped.array, self.registry)
            if read_from is not None:
                self._read_element(state, read_from, subject, loc)

    def _apply_call_facts(self, state: State, call: hir.AST, truth: bool | None) -> State | None:
        """The facts a call's result promises of its arguments: those of the arm
        `truth` (a boolean predicate), or the unconditional ones (`truth` None).
        `prefix.length <=? src.length` with the arguments substituted becomes a
        length bound, an order fact between lengths, or — for a tail argument
        `src[i..]` — a fact about `src.length - i`."""
        for refined in _call_result_refinements(call):
            for proposition in refined.propositions:
                if proposition.param is None or proposition.type_ is not None or proposition.when not in (truth, None):
                    continue
                if proposition.of != 'length':
                    continue
                subject_argument = _call_argument(call, proposition.param)
                if subject_argument is None:
                    continue
                subject_argument = _strip_casts(subject_argument)
                subject_length = self._length_interval(subject_argument, state)
                subject_id = _runtime_array_id(subject_argument, self.registry)
                gap = 1 if proposition.op == '<?' else 0
                if proposition.term is not None:
                    bound_argument = _call_argument(call, proposition.term)
                    if bound_argument is None:
                        continue
                    bound_argument = _strip_casts(bound_argument)
                    bound_id = _runtime_array_id(bound_argument, self.registry)
                    tail = self._tail_of(bound_argument) if bound_id is None else None
                    if proposition.op not in ('<?', '<=?'):
                        continue
                    if subject_length is not None and subject_length.lower is not None and subject_id is None:
                        # a known-length subject: the bound's length is at least that (plus the gap)
                        needed = subject_length.lower + gap
                        if bound_id is not None:
                            key = _length_key(bound_id)
                            state[key] = _known_interval(state, key, self.max_length).intersect(Interval(needed, None))
                        elif tail is not None:
                            key = _order_key(tail[1], _length_key(tail[0]))
                            previous = state.get(key)
                            state[key] = Interval(needed if previous is None or previous.lower is None else max(previous.lower, needed), None)
                    elif subject_id is not None:
                        if bound_id is not None:
                            state[_order_key(_length_key(subject_id), _length_key(bound_id))] = Interval(gap, None)
                        elif tail is not None:
                            state[_remainder_key(_length_key(subject_id), tail[0], tail[1])] = Interval(gap, None)
                elif subject_id is not None:
                    name = {'>?': '__gt__', '>=?': '__ge__', '<?': '__lt__', '<=?': '__le__', '=?': '__eq__', 'not=?': '__ne__'}.get(proposition.op)
                    constraint = self._comparison_constraint(name, Interval.exact(proposition.value), True) if name is not None else None
                    if constraint is not None:
                        key = _length_key(subject_id)
                        state[key] = _known_interval(state, key, self.max_length).intersect(constraint)
        return state

    def _shifted_facts(self, state: State, term: int, node: hir.Assign) -> dict[int, Interval]:
        """The order and remainder facts on `term` after `term += c` / `term -= c`,
        each gap moved by the constant (dropped when it would go negative)."""
        constant = self._constant_expr(node.value, set())
        if constant is None or constant.lower is None or constant.lower != constant.upper:
            return {}
        shift = constant.lower if node.op == '+=' else -constant.lower
        shifted: dict[int, Interval] = {}
        for key, interval in state.items():
            if interval.lower is None:
                continue
            order = _decode_order_fact(key)
            if order is not None and order[0] == term and interval.lower - shift >= 0:
                shifted[key] = Interval(interval.lower - shift, None)
                continue
            remainder = _decode_remainder_fact(key)
            if remainder is not None and remainder[2] == term and interval.lower - shift >= 0:
                shifted[key] = Interval(interval.lower - shift, None)
        return shifted

    def _seed_sum_facts(self, subject: int, value: hir.AST, state: State) -> None:
        """`let stop = i + length` under `length <= src.length - i`: `stop <= src.length`;
        `let last = prefix.length - 1`: what bounds `prefix.length` bounds `last` by one more."""
        value = _strip_casts(value)
        if not (isinstance(value, hir.FunctionCall) and isinstance(value.func, hir.ExpressedIdentifier) and value.func.name in ('__add__', '__sub__') and len(value.pos_args) == 2):
            return
        for term_node, constant_node, sign in ((value.pos_args[0], value.pos_args[1], 1), *(((value.pos_args[1], value.pos_args[0], 1),) if value.func.name == '__add__' else ())):
            constant = self._constant_expr(constant_node, set())
            term = self._binding_id(term_node)
            if term is None or constant is None or constant.lower is None or constant.lower != constant.upper:
                continue
            shift = constant.lower if value.func.name == '__add__' else -constant.lower   # subject = term + shift
            for key, interval in list(state.items()):
                if interval.lower is None:
                    continue
                order = _decode_order_fact(key)
                if order is not None and order[0] == term and order[1] != term:
                    if interval.lower - shift >= 0:
                        state[_order_key(subject, order[1])] = Interval(interval.lower - shift, None)
                    continue
                remainder = _decode_remainder_fact(key)
                if remainder is not None and remainder[0] == term and interval.lower - shift >= 0:
                    state[_remainder_key(subject, remainder[1], remainder[2])] = Interval(interval.lower - shift, None)
            return
        if value.func.name == '__sub__':
            # `let start = text.length - suffix.length` under `suffix.length <= text.length`
            # and `suffix.length >= k`: `start <= text.length - k`
            measured = _sequence_of(value.pos_args[0])
            sequence_id = _runtime_array_id(measured, self.registry) if measured is not None else None
            taken = self._binding_id(value.pos_args[1])
            if sequence_id is not None and taken is not None:
                bounded = self._id_bounded_by_length(taken, sequence_id, 0, state)   # no wrap: the subtrahend is within the length
                taken_interval = _known_interval(state, taken, self.max_length) if taken < 0 else self._binding_interval(state, taken)
                if bounded and taken_interval.lower is not None and taken_interval.lower >= 0:
                    state[_order_key(subject, _length_key(sequence_id))] = Interval(taken_interval.lower, None)
            return
        left_id, right_id = self._binding_id(value.pos_args[0]), self._binding_id(value.pos_args[1])
        if left_id is None or right_id is None or left_id < 0 or right_id < 0:
            return
        for key, interval in list(state.items()):
            remainder = _decode_remainder_fact(key)
            if remainder is not None and {remainder[0], remainder[2]} == {left_id, right_id} and interval.lower is not None:
                state[_order_key(subject, _length_key(remainder[1]))] = Interval(interval.lower, None)

    def _copy_relational_facts(self, state: State, source: int, target: int) -> None:
        """`let x = y`: the order, remainder, index and nonzero facts of `y` hold of `x`."""
        for key, interval in list(state.items()):
            remainder = _decode_remainder_fact(key)
            if remainder is not None:
                if remainder[0] == source:
                    state[_remainder_key(target, remainder[1], remainder[2])] = interval
                continue
            order = _decode_order_fact(key)
            if order is not None:
                if order[0] == source:
                    state[_order_key(target, order[1])] = interval
                continue
            index_fact = _decode_index_fact(key)
            if index_fact is not None and index_fact[0] == source:
                state[_index_fact_key(target, index_fact[1])] = interval

    # ---- element facts: what holds of every element of an array ----
    #
    # Facts about a value follow it into an array and back out: pushing a
    # record whose `length` field satisfies `length <= src.length - i` makes
    # that a fact of the element route `matches.*.length`; an element read
    # (`matches[0]`, `loop m in matches`) gives its own routes the facts; a
    # copy (`let matches = capture`) carries them; a push intersects (an
    # element without the fact drops it); an empty array has every fact.

    def _element_route(self, array_id: int, path: tuple[str, ...], loc: Span) -> int:
        return self.registry.route_id(array_id, ('*', *path), 'int64', loc)

    def _element_routes(self, array_id: int) -> list[int]:
        return self.registry.routes_under(array_id, ('*',))

    def _element_route_of(self, node: hir.AST) -> int | None:
        """The element route a read denotes: `xs[k].f` is `xs.*.f`, `xs[k]` is `xs.*`."""
        path: list[str] = []
        current = _strip_casts(node)
        while isinstance(current, hir.MemberAccess):
            path.append(current.name)
            current = _strip_casts(current.value)
        if not isinstance(current, hir.Index):
            return None
        array_id = _runtime_array_id(current.array, self.registry)
        if array_id is None:
            return None
        route = self.registry.route_ids.get((array_id, ('*', *reversed(path))))
        return route

    def _value_fact_sources(self, value: hir.AST) -> list[tuple[tuple[str, ...], int]]:
        """The fact-bearing parts of a value about to be stored: `(path, id)` — a
        record literal's binding-valued fields, a binding's routes, the binding itself."""
        value = _strip_casts(value)
        if isinstance(value, hir.ObjectLiteral):
            sources = []
            for item in value.fields:
                field_id = self._binding_id(item.value)
                if field_id is not None and field_id >= 0:
                    sources.append(((item.name,), field_id))
                    for route in self.registry.routes_under(field_id):
                        sources.append(((item.name, *self.registry.route_paths[route]), route))
            return sources
        source = self._binding_id(value)
        if source is None:
            source = self._element_route_of(value)
        if source is None or source < 0:
            return []
        sources = [((), source)]
        if isinstance(value, hir.ExpressedIdentifier):
            for route in self.registry.routes_under(source):
                sources.append((self.registry.route_paths[route], route))
        return sources

    def _facts_of(self, state: State, subject: int) -> dict[int, Interval]:
        """The relational facts whose subject is `subject`, keyed as they would be for subject 0."""
        facts: dict[int, Interval] = {}
        for key, interval in state.items():
            remainder = _decode_remainder_fact(key)
            if remainder is not None:
                if remainder[0] == subject:
                    facts[_remainder_key(0, remainder[1], remainder[2])] = interval
                continue
            order = _decode_order_fact(key)
            if order is not None:
                if order[0] == subject:
                    facts[_order_key(0, order[1])] = interval
                continue
            index_fact = _decode_index_fact(key)
            if index_fact is not None and index_fact[0] == subject:
                facts[_index_fact_key(0, index_fact[1])] = interval
        return facts

    @staticmethod
    def _rekey(key: int, subject: int) -> int:
        remainder = _decode_remainder_fact(key)
        if remainder is not None:
            return _remainder_key(subject, remainder[1], remainder[2])
        order = _decode_order_fact(key)
        if order is not None:
            return _order_key(subject, order[1])
        index_fact = _decode_index_fact(key)
        assert index_fact is not None
        return _index_fact_key(subject, index_fact[1])

    def _store_element(self, state: State, array_id: int, value: hir.AST, loc: Span) -> None:
        """An element joins the array: its facts become (or narrow) the element facts."""
        empty = state.get(_length_key(array_id)) == Interval.exact(0)
        stored: dict[int, dict[int, Interval]] = {}
        for path, source in self._value_fact_sources(value):
            stored[self._element_route(array_id, path, loc)] = self._facts_of(state, source)
        for route in self._element_routes(array_id):
            existing = self._facts_of(state, route)
            incoming = stored.get(route, {})
            for key, interval in existing.items():
                if key in incoming:
                    state[self._rekey(key, route)] = interval.union(incoming[key])
                elif not empty:
                    del state[self._rekey(key, route)]
        if empty:
            for route, facts in stored.items():
                for key, interval in facts.items():
                    state[self._rekey(key, route)] = interval

    def _read_element(self, state: State, array_id: int, target: int, loc: Span) -> None:
        """`let m = xs[k]`, `loop m in xs`: the element facts hold of `m` and its routes."""
        for route in self._element_routes(array_id):
            path = self.registry.route_paths[route][1:]
            subject = target if not path else self.registry.route_id(target, path, 'int64', loc)
            for key, interval in self._facts_of(state, route).items():
                state[self._rekey(key, subject)] = interval

    def _copy_element_facts(self, state: State, source: int, target: int, loc: Span) -> None:
        """`let matches = capture`: the element facts of one array hold of the other."""
        for route in self._element_routes(source):
            path = self.registry.route_paths[route]
            mirrored = self.registry.route_id(target, path, 'int64', loc)
            for key, interval in self._facts_of(state, route).items():
                state[self._rekey(key, mirrored)] = interval

    def _vacuous(self, state: State, key: int) -> bool:
        """Whether an element fact holds of `state` because the array is empty there."""
        remainder = _decode_remainder_fact(key)
        subject = remainder[0] if remainder is not None else None
        if subject is None:
            order = _decode_order_fact(key)
            if order is not None:
                subject = order[0]
            else:
                index_fact = _decode_index_fact(key)
                subject = index_fact[0] if index_fact is not None else None
        if subject is None or subject < 0:
            return False
        binding = self.registry.by_id.get(subject)
        if binding is None or binding.route_root is None or not self.registry.route_paths.get(subject, ()):
            return False
        if self.registry.route_paths[subject][0] != '*':
            return False
        return state.get(_length_key(binding.route_root)) == Interval.exact(0)

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
            sequence = node.array if isinstance(node, hir.Index) else node.string
            array_id = _runtime_array_id(sequence, self.registry)
            nonnegative = interval is not None and interval.lower is not None and interval.lower >= 0
            if array_id is not None and nonnegative:
                # the proven minimum: the length fact, tightened by a field's declared length bound
                minimum_length = (self._length_interval(sequence, state) or self._length_default()).lower or 0
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
        notes = []
        if length is None:
            notes.append(f'nothing establishes the {kind}\'s length here, so even a small index may be past the end')
        self._proof_failure(node, 'index', Error(
            srcfile=self.srcfile,
            title=f'{kind} index is not proven in bounds',
            pointer_messages=[Pointer(
                span=index.loc,
                message=f'the index interval here is `{known}`',
            )],
            notes=notes,
            hint=(
                (f'guard on the length first: `if xs.length >? {interval.upper} {{ … }}` proves a constant index, `i <? xs.length` a running one'
                 if length is None and interval is not None and interval.lower is not None and interval.lower >= 0
                 else f'establish both a nonnegative lower bound and an upper bound below the {kind} length')
            ),
        ))

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
                minimum = state.get(_length_key(string_id), self._length_default()).lower or 0

                def endpoint_proven(endpoint: hir.AST | None, interval: Interval | None, delta: int, limit: int) -> bool:
                    """`endpoint + delta` lies in `[-1 or 0, limit)` for every value, or an index fact bounds it."""
                    if endpoint is None:
                        return True
                    required_gap = delta if limit == minimum + 1 else 1 + delta
                    layout = ty.fixed_integer_layout(ty.strip_refinement(endpoint.type))
                    unsigned = layout is not None and not layout[1]
                    if (unsigned or (interval is not None and interval.lower is not None and interval.lower + delta >= (0 if delta >= 0 else -1))) and self._bounded_by_length(endpoint, string_id, required_gap, state):
                        return True   # `i + length` under `length <= src.length - i`, a refined call's result, …
                    if interval is None or interval.lower is None or interval.lower + delta < (0 if delta >= 0 else -1):
                        return False
                    if interval.upper is not None and interval.upper + delta < limit:
                        return True
                    binding = self._binding_id(endpoint)
                    if binding is not None and _index_fact_key(binding, string_id) in state:
                        return True
                    # an order fact against the length: `i <=? s.length` admits `i` as an
                    # exclusive end (`s[0..i)`) or a start; `i <? s.length` as an inclusive end
                    order = state.get(_order_key(binding, _length_key(string_id))) if binding is not None else None
                    if order is not None and order.lower is not None and order.lower >= required_gap:
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
                    # the whole chain, flattened: each conjunct refines in
                    # order, then one more pass so a fact a later conjunct
                    # established lets an earlier one say more
                    # (`start <=? last and last <? text.length`)
                    conjuncts = [*_conjuncts(condition.left), *_conjuncts(condition.right)]   # the root may be `nand`
                    current: State | None = refined
                    for _pass in range(2):
                        for conjunct in conjuncts:
                            current = self._refine(current, conjunct, truth=True)
                            if current is None:
                                return None
                    return current
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
        if isinstance(_strip_casts(condition), hir.FunctionCall) and _call_result_refinements(condition):
            # `if has_prefix(src[i..] opener)`: what the predicate promises of its arguments in this arm
            return self._apply_call_facts(refined, condition, truth)
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
        # `a <=? b` (or `a <? b`) between two bindings: whatever `b` is proven
        # below (`b <? xs.length`), `a` is too — the index facts chain
        ordered = {'__lt__': (left, right), '__le__': (left, right), '__gt__': (right, left), '__ge__': (right, left)}
        effective = name if truth else {'__gt__': '__le__', '__ge__': '__lt__', '__lt__': '__ge__', '__le__': '__gt__'}.get(name)
        if effective in ordered:
            smaller, larger = ordered[effective]
            smaller_id, larger_id = self._binding_id(smaller), self._binding_id(larger)
            if smaller_id is not None and larger_id is not None and smaller_id != larger_id:
                for key in list(refined):
                    decoded = _decode_index_fact(key)
                    if decoded is not None and decoded[0] == larger_id and decoded[1] != _NONZERO_MARK:
                        refined[_index_fact_key(smaller_id, decoded[1])] = Interval.exact(1)
                # and the comparison itself is kept: `larger - smaller >= gap`
                gap = 1 if effective in {'__lt__', '__gt__'} else 0
                refined[_order_key(smaller_id, larger_id)] = Interval(gap, None)
        if (name == '__eq__') == truth and name in {'__eq__', '__ne__'}:
            # `a =? b` holding (or `a not=? b` failing): each is at most the other
            left_id, right_id = self._binding_id(left), self._binding_id(right)
            if left_id is not None and right_id is not None and left_id != right_id:
                refined[_order_key(left_id, right_id)] = Interval(0, None)
                refined[_order_key(right_id, left_id)] = Interval(0, None)
        left_binding = self._binding_id(left)
        right_interval = self._eval(right, refined, validate=False)
        if _is_inequality(name, truth):
            # `n not=? text.length` (a failed `n =? text.length`) under `n <=? text.length`: `n <? text.length`
            left_term, right_term = self._binding_id(left), self._binding_id(right)
            if left_term is not None and right_term is not None and left_term != right_term:
                for smaller, larger in ((left_term, right_term), (right_term, left_term)):
                    order = refined.get(_order_key(smaller, larger))
                    if order is not None and order.lower == 0:
                        refined[_order_key(smaller, larger)] = Interval(1, order.upper)
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
                previous = self._binding_interval(refined, left_binding)
                narrowed = previous.intersect(constraint)
                if narrowed.is_empty:
                    return None
                refined[left_binding] = narrowed
            elif _is_inequality(name, truth) and right_interval.lower is not None and right_interval.lower == right_interval.upper:
                # `x not =? c` (or a failed `x =? c`) excludes `c`: it tightens a bound it sits on
                excluded = _exclude_value(_known_interval(refined, left_binding, self.max_length), right_interval.lower)
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
                previous = self._binding_interval(refined, right_binding)
                narrowed = previous.intersect(constraint)
                if narrowed.is_empty:
                    return None
                refined[right_binding] = narrowed
            elif _is_inequality(inverse, truth) and left_interval.lower is not None and left_interval.lower == left_interval.upper:
                excluded = _exclude_value(_known_interval(refined, right_binding, self.max_length), left_interval.lower)
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
        if (name == '__eq__' and truth) or (name == '__ne__' and not truth):
            # `x =? c` holding, or `x not=? c` failing: the value is `c`
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
        self.declared_refinements[node.binding_id] = node.annotation
        lower: int | None = None
        upper: int | None = None
        length_lower: int | None = None
        for proposition in node.annotation.propositions:
            if proposition.field is not None:
                # `let d:bigint<sign =? 1> = …`: facts on the field's route
                self._seed_field_proposition(node.binding_id, proposition, node.annotation.base, state, node.loc)
            elif proposition.subject == 'self':
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
            current = state.get(key, self._length_default())
            state[key] = current.intersect(Interval(length_lower, self.max_length))
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

    def _join_states(self, states: list[State]) -> State:
        if not states:
            return {}
        common = set(states[0])
        for state in states[1:]:
            common &= state.keys()
        # an element fact missing from a state where the array is empty holds there vacuously
        for key in set().union(*(state.keys() for state in states)) - common:
            if all(key in state or self._vacuous(state, key) for state in states):
                common.add(key)
        return {
            binding_id: _union_intervals(
                [state[binding_id] for state in states if binding_id in state]
            )
            for binding_id in common
        }

    def _narrow_states(self, head: State, candidate: State) -> State:
        """The head tightened by one more pass of the body (keys the pass lost are dropped)."""
        return {
            key: head[key].intersect(candidate[key]) if key in candidate else head[key]
            for key in head.keys() & (candidate.keys() | {key for key in head if self._vacuous(candidate, key)})
        }

    def _widen_states(self, previous: State, current: State) -> State:
        common = previous.keys() & current.keys()
        widened: State = {}
        for key in current.keys() - common:
            if self._vacuous(previous, key):
                widened[key] = current[key]   # the fact of an array that was still empty before
        for binding_id in common:
            interval = previous[binding_id].widen(current[binding_id])
            if _is_length_key(binding_id):
                # array lengths never leave [0, cap], even when widened
                interval = Interval(
                    0 if interval.lower is None else interval.lower,
                    self.max_length if interval.upper is None else interval.upper,
                )
            else:
                # nor a variable its width: a `uint64` counter widens to `[0, 2^64-1]`, not `[-∞, ∞]`
                declared = self._type_interval(binding_id)
                if declared is not None:
                    interval = interval.intersect(declared)
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
    *,
    target: str = 'x86_64',
    prototype_sites: 'dict[int, tuple[str, Error]] | None' = None,
) -> None:
    """Validate every dynamic array index against its source-position facts.

    With ``unfit`` given, abstract-integer values that cannot be proven to fit
    a 64-bit word are collected there (keyed by node id) for the representation
    pass instead of being reported as errors.
    """

    validator = _BoundsValidator(registry, srcfile, root, target=target)
    validator.unfit = unfit
    validator.prototype_sites = prototype_sites
    validator.validate(root)
    last_cap_notes.extend(validator.cap_notes)
