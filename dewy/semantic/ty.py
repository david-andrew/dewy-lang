from dataclasses import dataclass, field
from collections import defaultdict
from typing import Literal

"""
Candidate type names:
Top: 
- any
Bottom:
- bottom
- never
- noreturn
- empty
Dynamic:
- <dewy probably just won't support dynamic/runtime types>
- dyn

I think noreturn will be a separate case from bottom





"""

# Pillars of the type hierarchy
type TopType = Literal['any']
TOP_TYPE: TopType = 'any'
type BottomType = Literal['never']
BOTTOM_TYPE: BottomType = 'never'
type ExceptionType = Literal['exception']
EXCEPTION_TYPE: ExceptionType = 'exception' # parent of all things skipped/forwarded by safe navigation
type TypeType = Literal['type']
TYPE_TYPE: TypeType = 'type'


# Special Types that don't participate in type expressions or the type hierarchy.
type VoidType = Literal['void']  # things cannot be partially void. e.g. `T | void` will always be an error
VOID_TYPE: VoidType = 'void'
type InferredType = Literal['untyped']  # untyped if you want to explicitly indicate it should be inferred, but unannotated things are inferred by default
INFERRED_TYPE: InferredType = 'untyped'


# TODO: probably some sort of Effect base type for the effect system
# type NoReturnEffect = Literal['noreturn']
# NORETURN_EFFECT: NoReturnEffect = 'noreturn'  # NOTE: noreturn is an effect, not a type!




# Dataclasses for type expressions

type Primitive = str   # has to be in the _named_types set


@dataclass
class TypeAnd:
    """type intersection: T1 & T2"""
    items: list[TypeExpr]
    def __post_init__(self):
        assert len(self.items) > 1, f'TypeAnd must have at least two items, got {len(self.items)}'

@dataclass
class TypeOr:
    """type union: T1 | T2"""
    items: list[TypeExpr]
    def __post_init__(self):
        assert len(self.items) > 1, f'TypeOr must have at least two items, got {len(self.items)}'

@dataclass
class TypeNot:
    """type negation: ~T"""
    type: TypeExpr

@dataclass
class TypeParameterize:
    """type parameterization: T<A1 A2 ...>"""
    t: TypeExpr
    args: list[TypeExpr] #TODO: other stuff can be set here, though perhaps it doesn't affect the typing?


@dataclass(frozen=True)
class TypeVariable:
    """A symbolic type inside a generic type-alias body."""

    name: str
    bound: TypeExpr = TOP_TYPE


@dataclass(frozen=True)
class DimensionType:
    """A normalized physical dimension used only during type checking.

    Entries are sorted ``(base_dimension, exponent)`` pairs with zero
    exponents removed.  A dimension has no runtime representation.
    """

    powers: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class QuantityType:
    """A numeric runtime representation tagged with a physical dimension."""

    number: TypeExpr
    dimension: DimensionType


# Building blocks for FunctionType / OverloadType (not HIR params, not standalone types)

@dataclass
class PosOrKwArg:
    """One positional slot in a FunctionType, optionally addressable by name.

    ``required=False`` means the function supplies a default when a completed
    call leaves this slot unset. An absent name makes the slot position-only;
    this represents both internal callables and source parameters written as
    ``<name:type>``.
    """
    name: str | None
    type: TypeExpr
    required: bool = True
    place: bool = False

@dataclass
class KwOnlyArg:
    """One keyword-only slot in a FunctionType.

    Part of the function-type representation: name + accepted argument type +
    whether a call must supply it. Optional when the surface param has a default;
    required for bare post-`...` kwargs (e.g. forced overwrite via `=void`).
    """
    name: str
    type: TypeExpr
    required: bool
    place: bool = False

@dataclass
class GenericParam:
    """A generic type variable declared on a FunctionType (e.g. T in `<T of number>`).

    Part of the function-type representation, not a TypeExpr by itself and not
    TypeParameterize (which is applying args like `array<int>`).
    Bound at call sites via infer_type_args / instantiate_method.
    """
    name: str
    bound: TypeExpr = TOP_TYPE


@dataclass
class GenericTypeAlias:
    """A compile-time type constructor expanded by ``Alias<args...>``."""

    params: list[GenericParam]
    body: TypeExpr

@dataclass
class FunctionType:
    """Type of a single callable: signature shape + return type.

    Built from PosOrKwArg / KwOnlyArg / GenericParam slots (and optional rest).
    This is a TypeExpr atom used in subtyping and dispatch, not an HIR function value.
    """
    pos_or_kw: list[PosOrKwArg]
    kw_only: list[KwOnlyArg]
    rest: str | None  # rest param name, or None
    ret: TypeExpr
    type_params: list[GenericParam] = field(default_factory=list)

@dataclass
class OverloadType:
    """Type of an overloaded callable: an ordered set of FunctionType alternatives.

    Produced by combining callables with `and`/`&` (i.e. function overloading). Still a
    TypeExpr atom; dispatch picks one method at each call site.
    """
    methods: list[FunctionType]
    # def __post_init__(self):
    #     assert len(self.methods) >= 1, 'OverloadType must have at least one method'


@dataclass
class SequenceType:
    """Multiple values in a sequence: (T1 T2 ... Tn). Use the sequence() smart constructor to build these."""
    items: list[TypeExpr]
    def __post_init__(self):
        assert len(self.items) > 1, f'SequenceType must have at least two items, got {len(self.items)}. 0/1-item sequences collapse to void/the item via sequence()'


@dataclass(frozen=True)
class IntegerLiteralType:
    """The singleton type inhabited by exactly one mathematical integer value."""
    value: int


@dataclass(frozen=True)
class StringLiteralType:
    """The singleton type inhabited by one exact Unicode scalar sequence."""

    value: str


@dataclass(frozen=True)
class BinaryLiteralType:
    """The singleton type inhabited by one exact byte sequence."""

    value: bytes


@dataclass(frozen=True)
class StringType:
    """An immutable grapheme sequence, optionally refined to an exact length."""

    length: int | None = None


@dataclass(frozen=True)
class ArrayType:
    """A homogeneous mutable array, optionally refined to an exact length."""

    element: TypeExpr
    length: int | None = None


@dataclass(frozen=True)
class ObjectField:
    """One named field in source order.

    ``default`` is the field's default expression (parser syntax, kept opaque
    here) when the type declares one: calling the type as a constructor may
    omit the field. Defaults do not take part in type identity.
    """

    name: str
    type: TypeExpr
    mutable: bool = True
    default: object = field(default=None, compare=False, hash=False)


@dataclass
class MethodSpec:
    """A method declared in an object type (`name = (params) => body`).

    Compiled as a hidden module-level function taking the instance as its
    first parameter `self` (a place when the body assigns fields); the
    checker fills ``binding_id`` when it declares that function.
    """

    name: str
    literal: object  # the `(params) => body` syntax
    binding_id: int | None = None
    place_self: bool = False


@dataclass(frozen=True)
class ObjectType:
    """A structural object whose field order is part of the type.

    ``brand`` names a compiler-provided object family that is distinct from
    any structurally identical user object: ``'dict'`` is the runtime
    dictionary ``[keys:array<K> values:array<V>]``.
    """

    fields: tuple[ObjectField, ...]
    brand: str | None = None
    methods: tuple[MethodSpec, ...] = field(default=(), compare=False, hash=False)
    """Methods declared in the type; not part of structural identity."""
    constructors: list[int] = field(default_factory=list, compare=False, hash=False)
    """Binding ids of `&=` constructor overloads, in declaration order."""

    def method(self, name: str) -> 'MethodSpec | None':
        return next((m for m in self.methods if m.name == name), None)

    def field(self, name: str) -> ObjectField | None:
        for object_field in self.fields:
            if object_field.name == name:
                return object_field
        return None


@dataclass(frozen=True)
class PathType(ObjectType):
    """A thin path object containing its lexical text."""


@dataclass(frozen=True, eq=False, repr=False)
class NamedType:
    """A by-name reference to a recursive type alias.

    ``let Node:type = [value:int64 next:Node|undefined]`` cannot be a finite
    structural tree, so the recursive occurrence is this reference; it unfolds
    to the alias's object type on demand (``target``). Two references to the
    same alias are equal. A reference may only appear as a union member, where
    the lowering stores the member behind a handle; expression types are
    always unfolded (see ``unfold``).
    """

    name: str
    alias_id: int
    _target: list[TypeExpr] = field(default_factory=list, compare=False, hash=False)

    @property
    def target(self) -> TypeExpr:
        if not self._target:
            raise ValueError(f'INTERNAL ERROR: recursive type `{self.name}` used before its alias resolved')
        return self._target[0]

    def resolve(self, target: TypeExpr) -> None:
        self._target[:] = [target]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, NamedType) and other.alias_id == self.alias_id

    def __hash__(self) -> int:
        return hash(('NamedType', self.alias_id))

    def __repr__(self) -> str:
        return f'NamedType({self.name!r})'


def unfold(type_: Type) -> Type:
    """An expression-level type: a recursive reference becomes its object type."""
    return type_.target if isinstance(type_, NamedType) else type_


def mentions_named_type(type_: object) -> bool:
    """Whether a type contains a recursive reference anywhere (without unfolding it)."""
    if isinstance(type_, NamedType):
        return True
    if isinstance(type_, (TypeOr, TypeAnd)):
        return any(mentions_named_type(item) for item in type_.items)
    if isinstance(type_, TypeNot):
        return mentions_named_type(type_.type)
    if isinstance(type_, ObjectType):
        return any(mentions_named_type(field.type) for field in type_.fields)
    if isinstance(type_, ArrayType):
        return mentions_named_type(type_.element)
    if isinstance(type_, RefinedType):
        return mentions_named_type(type_.base)
    if isinstance(type_, FunctionType):
        return any(mentions_named_type(p.type) for p in [*type_.pos_or_kw, *type_.kw_only]) or mentions_named_type(type_.ret)
    return False


@dataclass(frozen=True, init=False)
class PathLiteralType(PathType):
    """The singleton type inhabited by one exact lexical path."""

    value: str

    def __init__(self, value: str):
        object.__setattr__(
            self,
            'fields',
            (ObjectField('path', StringLiteralType(value)),),
        )
        object.__setattr__(self, 'value', value)


PATH_TYPE = PathType((ObjectField('path', StringType()),))


@dataclass(frozen=True)
class ModuleField:
    """One compile-time member exported by a source module."""

    name: str
    type: TypeExpr
    binding_id: int
    type_value: TypeAliasValue | None = None


@dataclass(frozen=True)
class ModuleType:
    """A compile-time namespace; it has no runtime representation."""

    fields: tuple[ModuleField, ...]

    def field(self, name: str) -> ModuleField | None:
        return next((field for field in self.fields if field.name == name), None)


type TypeExpr = Primitive | TypeAnd | TypeOr | TypeNot | TypeParameterize | TypeVariable | DimensionType | QuantityType | FunctionType | OverloadType | SequenceType | IntegerLiteralType | RationalLiteralType | RefinedType | StringLiteralType | BinaryLiteralType | StringType | ArrayType | ObjectType | PathType | PathLiteralType | ModuleType | NamedType
type Type = TypeExpr | VoidType | InferredType # | NoReturnEffect # probably won't ever have a dynamic type, but if we did, it would also go here
type TypeAliasValue = TypeExpr | GenericTypeAlias




USER_NOMINAL_TYPES: dict[str, str] = {}
"""Nominal types minted by programs (`let NotFound:type = type of error`),
name -> parent. Every `TypeSystem` registers them, so the lowering's fresh
instances agree with the checker's about `NotFound of? error`."""


def is_user_nominal(type_: object) -> bool:
    return isinstance(type_, str) and type_ in USER_NOMINAL_TYPES


# some types to add:
# insert basic types into the system
# note, things like partial order, comparable, etc. will be represented in the structural type system, not the type graph
# TODO: do we support multiple inheritance? probably but TBD
_default_system_types: list[Primitive|tuple[Primitive, Primitive]] = [
    # exceptions
    ('undefined', EXCEPTION_TYPE),
    ('error', EXCEPTION_TYPE),

    # basic types
    'ellipsis',
    'end',
    'new',
    'bool',

    # numbers
    'number',
    ('real', 'number'),
    ('rational', 'real'),
    ('int', 'rational'),
    ('uint', 'int'),
    ('uint8', 'uint'),
    ('uint16', 'uint'),
    ('uint32', 'uint'),
    ('uint64', 'uint'),
    # ('uint128', 'uint'),
    ('int8', 'int'),
    ('int16', 'int'),
    ('int32', 'int'),
    ('int64', 'int'),
    # ('int128', 'int'),
    # Floating-point values are approximate representations of real numbers.
    # Keeping them under `real` lets APIs such as Duration<T of real> accept
    # both integral and floating-point representations while still excluding
    # complex and quaternion values.
    ('float', 'real'),
    # ('float8', 'float'),
    # ('float16', 'float'),
    ('float32', 'float'),
    ('float64', 'float'),
    # ('float80', 'float'),
    # ('float128', 'float'),
    ('complex', 'number'),   # note: parameterized by the type of its internal representation
    ('quaternion', 'number'), # note: parameterized by the type of its internal representation

    'function',
    'multifunction',
    'generator',
    'iterator',
    'multiiterator',
    'range',
    'multirange',

    # container types
    'array',
    'dict',
    'set',
    'object',

    # strings are immutable grapheme sequences; char is the one-grapheme alias
    'string',
    ('grapheme', 'string'),
    ('char', 'grapheme'),
    # 'istring',  # string with interpolated values. istring probably isn't a separate type? since it should be interchangable with strings
    
    # tbd misc stuff
    'ID' # a generic thing representing some way to identify something. implementations may use specific data types like int, string, etc., but conceptually an ID is basically it's own separate thing
]

@dataclass(frozen=True)
class Proposition:
    """One liquid refinement condition, `<subject> <op> <value>`.

    ``subject`` is ``'self'`` (the value itself, written with a one-argument
    lambda such as `i => i >? 0` or with the declared name), ``'length'`` (a
    container length), or ``'.name'`` (an integer field of an object value:
    `r:Ratio<bottom >? 0>`).
    """

    subject: str
    op: str
    value: int

    @property
    def field(self) -> str | None:
        """The field name of a field subject, else None."""
        return self.subject[1:] if self.subject.startswith('.') else None

    def holds(self, fact: int) -> bool:
        match self.op:
            case '>?': return fact > self.value
            case '>=?': return fact >= self.value
            case '<?': return fact < self.value
            case '<=?': return fact <= self.value
            case '=?': return fact == self.value
            case 'not=?': return fact != self.value
        raise ValueError(f'INTERNAL ERROR: unknown proposition operator {self.op!r}')

    def lower_bound(self) -> int | None:
        """The minimum value this proposition guarantees, if it is a lower bound."""
        if self.op == '>?':
            return self.value + 1
        if self.op in {'>=?', '=?'}:
            return self.value
        return None

    def upper_bound(self) -> int | None:
        if self.op == '<?':
            return self.value - 1
        if self.op in {'<=?', '=?'}:
            return self.value
        return None


@dataclass(frozen=True)
class RefinedType:
    """A type together with liquid propositions its values must satisfy.

    Refined types appear in annotations only: checking a value against one
    proves the propositions from compile-time facts, and the binding then
    carries the base type plus the proven facts.
    """

    base: TypeExpr
    propositions: tuple[Proposition, ...]


def dict_type(key: TypeExpr, value: TypeExpr) -> ObjectType:
    """The runtime dictionary object for `dict<K V>`: parallel entry arrays in insertion order.

    Entry types are canonical so literal-inferred and annotated dictionaries
    agree: any string representation is the primitive ``string`` (exact
    lengths of literal keys are not part of the dictionary's type).
    """
    def canonical(type_: TypeExpr) -> TypeExpr:
        if isinstance(type_, (StringType, StringLiteralType)):
            return 'string'
        return type_
    return ObjectType(
        (
            ObjectField('keys', ArrayType(canonical(key), None)),
            ObjectField('values', ArrayType(canonical(value), None)),
            # compact-dict machinery: per-entry hashes (-1 marks a removed
            # entry), the power-of-two probe table (-1 empty, -2 dummy, else
            # an entry index), and the live entry count
            ObjectField('hashes', ArrayType('int64', None)),
            ObjectField('indices', ArrayType('int64', None)),
            ObjectField('live', 'int64'),
        ),
        'dict',
    )


def set_type(element: TypeExpr) -> ObjectType:
    """The runtime set object for `set<T>`: a dictionary without values (same table machinery)."""
    def canonical(type_: TypeExpr) -> TypeExpr:
        if isinstance(type_, (StringType, StringLiteralType)):
            return 'string'
        return type_
    return ObjectType(
        (
            ObjectField('keys', ArrayType(canonical(element), None)),
            ObjectField('hashes', ArrayType('int64', None)),
            ObjectField('indices', ArrayType('int64', None)),
            ObjectField('live', 'int64'),
        ),
        'set',
    )


def set_element(type_: TypeExpr) -> TypeExpr | None:
    """`T` when ``type_`` is a runtime set object."""
    if isinstance(type_, ObjectType) and type_.brand == 'set':
        keys = type_.fields[0].type
        assert isinstance(keys, ArrayType)
        return keys.element
    return None


def container_entry_types(type_: TypeExpr) -> tuple[TypeExpr, TypeExpr | None] | None:
    """`(K, V)` for a dictionary, `(T, None)` for a set, else None."""
    key_value = dict_key_value(type_)
    if key_value is not None:
        return key_value
    element = set_element(type_)
    if element is not None:
        return element, None
    return None


def dict_key_value(type_: TypeExpr) -> tuple[TypeExpr, TypeExpr] | None:
    """`(K, V)` when ``type_`` is a runtime dictionary object."""
    if isinstance(type_, ObjectType) and type_.brand == 'dict':
        keys, values = type_.fields[0].type, type_.fields[1].type
        assert isinstance(keys, ArrayType) and isinstance(values, ArrayType)
        return keys.element, values.element
    return None


def strip_refinement(type_: TypeExpr) -> TypeExpr:
    return type_.base if isinstance(type_, RefinedType) else type_


@dataclass(frozen=True)
class RationalLiteralType:
    """The singleton type of one exact compile-time rational (normalized)."""

    numerator: int
    denominator: int


# map from structural python types to their nominal position in the type graph 
STRUCTURAL_NOMINAL_MAP: dict[type, Primitive] = {
    FunctionType: 'function',
    OverloadType: 'multifunction',
    SequenceType: 'generator',  # a group of expressed values is consumable like a generator; only the bare umbrella, `<int int> of? generator<int>` is TBD
    IntegerLiteralType: 'int',
    RationalLiteralType: 'rational',
    StringLiteralType: 'string',
    StringType: 'string',
    ArrayType: 'array',
    ObjectType: 'object',
    PathType: 'object',
    PathLiteralType: 'object',
    NamedType: 'object',

    # TBD about these
    # IteratorType: 'iterator',
    # MultiIteratorType: 'multiiterator',
    # RangeType: 'range',
    # MultiRangeType: 'multirange',

    # also TBD about if the container types also go in here?
}


_fixed_integer_widths: dict[str, tuple[int, bool]] = {
    'uint8': (8, False),
    'uint16': (16, False),
    'uint32': (32, False),
    'uint64': (64, False),
    'int8': (8, True),
    'int16': (16, True),
    'int32': (32, True),
    'int64': (64, True),
}

FIXED_INTEGER_TYPES = frozenset(_fixed_integer_widths)


def optional_payload(type_: Type) -> TypeExpr | None:
    """Return the sole non-undefined member of ``T | undefined``."""

    if not isinstance(type_, TypeOr) or 'undefined' not in type_.items:
        return None
    payloads = [item for item in type_.items if item != 'undefined']
    return payloads[0] if len(payloads) == 1 else None


def optional(type_: TypeExpr) -> TypeExpr:
    """Construct the canonical optional form for one payload type."""

    return union(type_, 'undefined')


def runtime_union_members(type_: Type) -> tuple[TypeExpr, ...] | None:
    """Canonical member order for a general runtime tagged union.

    Returns None for non-unions and for single-payload optionals, which keep
    their dedicated two-state cells. ``undefined`` is always member 0 when
    present, so the general tag numbering coincides with optional tags.
    """
    if not isinstance(type_, TypeOr):
        return None
    if optional_payload(type_) is not None:
        return None
    # Canonical order: `undefined` first, then a deterministic sort, so every
    # spelling of the same member set (declared, narrowed, joined) numbers
    # its tags identically.
    members = sorted(
        type_.items,
        key=lambda member: (0 if member == 'undefined' else 1, repr(member)),
    )
    return tuple(members)


def is_zero_arg_function(type_: Type) -> bool:
    """Whether a type is a function that takes no arguments."""

    return (
        isinstance(type_, FunctionType)
        and not type_.pos_or_kw
        and not type_.kw_only
        and type_.rest is None
    )


def fixed_integer_layout(type_: TypeExpr) -> tuple[int, bool] | None:
    """Return `(bit_width, signed)` for a concrete fixed-width integer."""

    return _fixed_integer_widths.get(type_) if isinstance(type_, str) else None


def integer_literal_fits(value: int, target: Primitive) -> bool:
    """Whether `value` is a valid mathematical instance of an integer type."""
    if target == 'int':
        return True
    if target == 'uint':
        return value >= 0
    spec = _fixed_integer_widths.get(target)
    if spec is None:
        return False
    width, signed = spec
    if signed:
        return -(1 << (width - 1)) <= value < (1 << (width - 1))
    return 0 <= value < (1 << width)


def string_literal_lengths(value: str) -> tuple[int, int, int]:
    """Return UTF-8 byte, Unicode scalar, and grapheme counts for a literal."""

    from .unicode.graphemes import grapheme_count

    return len(value.encode('utf-8')), len(value), grapheme_count(value)


def dimension(*powers: tuple[str, int]) -> DimensionType:
    """Build a canonical dimension from possibly repeated base powers."""

    combined: dict[str, int] = defaultdict(int)
    for name, exponent in powers:
        combined[name] += exponent
    return DimensionType(tuple(
        (name, exponent)
        for name, exponent in sorted(combined.items())
        if exponent
    ))


def multiply_dimensions(left: DimensionType, right: DimensionType) -> DimensionType:
    return dimension(*left.powers, *right.powers)


def divide_dimensions(left: DimensionType, right: DimensionType) -> DimensionType:
    return dimension(*left.powers, *((name, -exponent) for name, exponent in right.powers))


def power_dimension(base: DimensionType, exponent: int) -> DimensionType:
    return dimension(*((name, power * exponent) for name, power in base.powers))


class TypeSystem:
    def __init__(self, system_types: list[Primitive|tuple[Primitive, Primitive]] = _default_system_types):
        self._named_types: set[str] = {TOP_TYPE, BOTTOM_TYPE, EXCEPTION_TYPE, TYPE_TYPE} # void and inferred don't participate in type expressions
        self._type_parents: dict[str, set[str]] = defaultdict(set, {BOTTOM_TYPE: {TOP_TYPE}, EXCEPTION_TYPE: {TOP_TYPE}, TYPE_TYPE: {TOP_TYPE}})
        self._type_children: dict[str, set[str]] = defaultdict(set, {TOP_TYPE: {BOTTOM_TYPE, EXCEPTION_TYPE, TYPE_TYPE}})
        # order-independent keys via sorted (a, b); separate from the subtype graph
        self._promote_rules: dict[tuple[str, str], str] = {}
        # Runtime representations of `rational`/`fixed`, registered from the
        # prelude's object types so compile-time numbers dispatch onto them.
        self.rational_object: TypeExpr | None = None
        self.fixed_object: TypeExpr | None = None
        self.bigint_object: TypeExpr | None = None

        for t in system_types:
            if isinstance(t, tuple): self.add_type(*t) 
            else: self.add_type(t)
        self.register_user_nominals()

    def add_type(self, name: str, parent: str = TOP_TYPE) -> None:
        if name in self._named_types:
            raise ValueError(f'Type {name} already defined')
        self._named_types.add(name)
        self.add_type_link(name, parent)

    def register_user_nominals(self) -> None:
        """Adopt every program-minted nominal type not yet known here."""
        for name, parent in USER_NOMINAL_TYPES.items():
            if name not in self._named_types and parent in self._named_types:
                self.add_type(name, parent)

    def add_type_link(self, child: str, parent: str) -> None:
        if child not in self._named_types:
            raise ValueError(f'Type {child} not defined')
        if parent not in self._named_types:
            raise ValueError(f'Type {parent} not defined')
        self._type_parents[child].add(parent)
        self._type_children[parent].add(child)

    def add_promote_rule(self, a: str, b: str, result: str) -> None:
        """Register promote_type(a, b) == result (order-independent). Extensible for user types."""
        if a not in self._named_types:
            raise ValueError(f'Type {a} not defined')
        if b not in self._named_types:
            raise ValueError(f'Type {b} not defined')
        if result not in self._named_types:
            raise ValueError(f'Type {result} not defined')
        self._promote_rules[tuple(sorted((a, b)))] = result

    def promote_type(self, a: TypeExpr, b: TypeExpr) -> Primitive | None:
        """Common concrete type for heterogeneous arithmetic, or None if none exists.

        Along-edge: if one is a nominal subtype of the other, return the wider.
        Cross-branch: look up an explicit promote rule. Not a lub in the type graph.
        """
        if not isinstance(a, str) or not isinstance(b, str):
            return None
        if a == b:
            return a
        for abstract, other in ((a, b), (b, a)):
            if abstract in {'int', 'uint'} and other in FIXED_INTEGER_TYPES:
                # An arbitrary-precision integer meeting a fixed width takes that
                # representation; the bounds analysis proves the value fits.
                return other
        if self._is_nom_subtype(a, b):
            return b
        if self._is_nom_subtype(b, a):
            return a
        return self._promote_rules.get(tuple(sorted((a, b))))
    
    # ---------------------------------------------------------------------------
    # Nominal type theory
    # ---------------------------------------------------------------------------

    def is_subtype(self, s: TypeExpr, t: TypeExpr) -> bool:
        """Top-level type checking function. `s of? t` => `is_empty(s & ~t)`"""
        return self.is_empty(intersect(s, negate(t)))


    def _is_nom_subtype(self, a: Primitive, b: Primitive) -> bool:
        if a == b:
            return True
        frontier = [a]
        seen = {a}
        while frontier:
            cur = frontier.pop()
            for parent in self._type_parents[cur]:
                if parent == b:
                    return True
                if parent not in seen:
                    seen.add(parent)
                    frontier.append(parent)
        return False


    def _meet_prim(self, a: Primitive, b: Primitive) -> Primitive | None:
        """GLB for tree-ish nominal DAG. None => disjoint / uninhabited."""
        if self._is_nom_subtype(a, b):
            return a
        if self._is_nom_subtype(b, a):
            return b
        return None  # unrelated => empty (v1)


    def _structural_nominal(self, atom: LiteralAtom) -> Primitive | None:
        """Nominal umbrella for a structural TypeExpr atom, if any."""
        return STRUCTURAL_NOMINAL_MAP.get(type(atom))


    def _meet_atoms(self, a: LiteralAtom, b: LiteralAtom) -> LiteralAtom | None:
        """
        Positive meet of two atoms.
        Covariant TypeParam:
        F<A> & G<B>  (F of? G)  =>  F<A & B>
        F<A> & G<B>  (G of? F)  =>  G<A & B>
        unrelated heads          =>  None (empty)
        Bare prim meets param by treating bare as head with no arg constraint
        array & array<int> => array<int>   if heads meet to array
        Structural & its nominal (or ancestor) => structural; two structurals only if equal.
        """
        if isinstance(a, TypeVariable):
            if a == b or self.is_subtype(a.bound, b):
                return a
            return None
        if isinstance(b, TypeVariable):
            if a == b or self.is_subtype(b.bound, a):
                return b
            return None
        if isinstance(a, NamedType) or isinstance(b, NamedType):
            if a == b:
                return a
            met = self._meet_atoms(unfold(a), unfold(b))
            if met is None:
                return None
            # keep the reference when it survives the meet, so union member
            # lists stay spelled by reference
            if isinstance(a, NamedType) and met == unfold(a):
                return a
            if isinstance(b, NamedType) and met == unfold(b):
                return b
            return met
        if isinstance(a, RefinedType) or isinstance(b, RefinedType):
            if a == b:
                return a
            refined, other = (a, b) if isinstance(a, RefinedType) else (b, a)
            return refined if self._meet_atoms(refined.base, other) == refined.base else None
        for literal, other in ((a, b), (b, a)):
            if (
                isinstance(literal, (IntegerLiteralType, RationalLiteralType))
                and isinstance(other, ObjectType)
                and other in (self.rational_object, self.fixed_object, self.bigint_object)
            ):
                return literal  # the compile-time number materializes into that representation
            if (
                isinstance(literal, str)
                and isinstance(other, ObjectType)
                and other == self.bigint_object
                and other is not None
                and self._is_nom_subtype(literal, 'int')
            ):
                return literal  # integers widen into big integers
        if isinstance(a, IntegerLiteralType) and isinstance(b, IntegerLiteralType):
            return a if a == b else None
        if isinstance(a, RationalLiteralType) and isinstance(b, RationalLiteralType):
            return a if a == b else None
        if isinstance(a, RationalLiteralType) and isinstance(b, str):
            return a if self._is_nom_subtype('rational', b) else None
        if isinstance(b, RationalLiteralType) and isinstance(a, str):
            return b if self._is_nom_subtype('rational', a) else None
        if isinstance(a, IntegerLiteralType) and isinstance(b, str):
            return a if self._integer_literal_implies(a, b) else None
        if isinstance(b, IntegerLiteralType) and isinstance(a, str):
            return b if self._integer_literal_implies(b, a) else None
        if isinstance(a, StringLiteralType):
            return a if self._string_literal_implies(a, b) else None
        if isinstance(b, StringLiteralType):
            return b if self._string_literal_implies(b, a) else None
        if isinstance(a, BinaryLiteralType):
            return a if self._binary_literal_implies(a, b) else None
        if isinstance(b, BinaryLiteralType):
            return b if self._binary_literal_implies(b, a) else None
        if isinstance(a, PathLiteralType):
            return a if self._path_literal_implies(a, b) else None
        if isinstance(b, PathLiteralType):
            return b if self._path_literal_implies(b, a) else None
        if isinstance(a, PathType) and isinstance(b, ObjectType):
            return a if self._path_type_implies(a, b) else None
        if isinstance(b, PathType) and isinstance(a, ObjectType):
            return b if self._path_type_implies(b, a) else None
        if isinstance(a, StringType) and isinstance(b, StringType):
            if a.length is None:
                return b
            if b.length is None:
                return a
            return a if a.length == b.length else None
        if isinstance(a, DimensionType) and isinstance(b, DimensionType):
            return a if a == b else None
        if isinstance(a, QuantityType) and isinstance(b, QuantityType):
            if a.dimension != b.dimension:
                return None
            number = intersect(a.number, b.number)
            if self.is_empty(number):
                return None
            return QuantityType(number, a.dimension)
        if isinstance(a, ArrayType) and isinstance(b, ArrayType):
            if a.element != b.element:
                return None
            if a.length is None:
                return b
            if b.length is None:
                return a
            return a if a.length == b.length else None
        if isinstance(a, ObjectType) and isinstance(b, ObjectType):
            return a if a == b else None
        if isinstance(a, ModuleType) and isinstance(b, ModuleType):
            return a if a == b else None

        a_nom = self._structural_nominal(a)
        b_nom = self._structural_nominal(b)

        # two sequences meet pointwise iff same arity; must come before the structural-equality fallback
        if isinstance(a, SequenceType) and isinstance(b, SequenceType):
            if len(a.items) != len(b.items):
                return None
            met = [intersect(x, y) for x, y in zip(a.items, b.items)]
            if any(self.is_empty(m) for m in met):
                return None
            return SequenceType(met)

        # FunctionType & function (or any) => FunctionType; siblings => empty
        if a_nom is not None and isinstance(b, str):
            return a if self._is_nom_subtype(a_nom, b) else None
        if b_nom is not None and isinstance(a, str):
            return b if self._is_nom_subtype(b_nom, a) else None
        if a_nom is not None or b_nom is not None:
            # two structural atoms, or structural & TypeParameterize
            if a_nom is not None and b_nom is not None:
                return a if a == b else None
            return None

        ha, hb = _head_of(a), _head_of(b)
        pa, pb = _as_prim_head(ha), _as_prim_head(hb)
        if pa is None or pb is None:
            # v1: non-primitive heads unsupported / only equal opaque heads
            if ha == hb and _args_of(a) == _args_of(b):
                return a
            return None

        head_meet = self._meet_prim(pa, pb)
        if head_meet is None:
            return None

        args_a, args_b = _args_of(a), _args_of(b)
        if not args_a and not args_b:
            return head_meet
        if not args_a:
            # bare F & G<B...> => head_meet<B...>  (e.g. collection & array<int> => array<int>)
            return TypeParameterize(head_meet, args_b)
        if not args_b:
            return TypeParameterize(head_meet, args_a)

        if len(args_a) != len(args_b):
            return None  # arity mismatch => empty

        # covariant: intersect args pointwise
        meet_args = [intersect(x, y) for x, y in zip(args_a, args_b)]
        # if any arg intersect is never, whole param is never
        if any(self.is_empty(arg) for arg in meet_args):
            # array<never> — treat as empty type in v1 (no values)
            return None
        return TypeParameterize(head_meet, meet_args)


    def _atom_implies_atom(self, a: LiteralAtom, b: LiteralAtom) -> bool:
        """
        Positive atom a is subtype of positive atom b.
        Covariant:
        F<A...> of? G<B...>  ⟺  (F of? G) and all (Ai of? Bi)
        F<A...> of? G        ⟺  F of? G
        F of? G<B...>        ⟺  false   (open world; can't invent args)
        Structural atoms also imply their STRUCTURAL_NOMINAL_MAP umbrella (and ancestors).
        """
        if isinstance(a, TypeVariable):
            return a == b or self.is_subtype(a.bound, b)
        if isinstance(b, TypeVariable):
            return a == b
        if isinstance(a, NamedType) or isinstance(b, NamedType):
            # a recursive reference stands for its alias's object type; equal
            # references short-circuit so unfolding always terminates
            if a == b:
                return True
            return self._atom_implies_atom(unfold(a), unfold(b))
        if isinstance(a, RefinedType):
            return a == b or self.is_subtype(a.base, b)
        if isinstance(b, RefinedType):
            # applicable on the base type; the refinement is an obligation
            # proven at the checking boundary (`check_against`), never assumed
            return self.is_subtype(a, b.base)
        if isinstance(a, (IntegerLiteralType, RationalLiteralType)) and isinstance(b, ObjectType):
            # Compile-time numbers materialize into the runtime rational,
            # fixed, or big-integer representation at the checking boundary.
            if b == self.fixed_object:
                return True
            if b == self.rational_object:
                return True
            if b == self.bigint_object:
                return isinstance(a, IntegerLiteralType)
            return False
        if isinstance(a, str) and isinstance(b, ObjectType) and b == self.bigint_object and b is not None:
            # every integer widens into a big integer without loss
            return self._is_nom_subtype(a, 'int')
        if isinstance(a, IntegerLiteralType):
            if isinstance(b, IntegerLiteralType):
                return a == b
            if isinstance(b, str):
                return self._integer_literal_implies(a, b)
        if isinstance(a, RationalLiteralType):
            if isinstance(b, RationalLiteralType):
                return a == b
            if isinstance(b, str):
                return self._is_nom_subtype('rational', b)
        if isinstance(a, StringLiteralType):
            return self._string_literal_implies(a, b)
        if isinstance(a, BinaryLiteralType):
            return self._binary_literal_implies(a, b)
        if isinstance(a, PathLiteralType):
            return self._path_literal_implies(a, b)
        if isinstance(a, PathType) and isinstance(b, ObjectType):
            return self._path_type_implies(a, b)
        if isinstance(a, StringType):
            if isinstance(b, StringType):
                return b.length is None or a.length == b.length
            if isinstance(b, str):
                if b in {'char', 'grapheme'}:
                    return a.length == 1
                return self._is_nom_subtype('string', b)
        if isinstance(a, DimensionType):
            return a == b or b == TOP_TYPE
        if isinstance(a, QuantityType):
            if isinstance(b, QuantityType):
                return (
                    a.dimension == b.dimension
                    and self.is_subtype(a.number, b.number)
                )
            return b == TOP_TYPE
        if isinstance(a, ArrayType) and isinstance(b, ArrayType):
            return (
                a.element == b.element
                and (b.length is None or a.length == b.length)
            )
        if isinstance(a, ObjectType) and isinstance(b, ObjectType):
            return a == b
        if isinstance(a, ModuleType) and isinstance(b, ModuleType):
            return a == b

        a_nom = self._structural_nominal(a)
        if a_nom is not None and isinstance(b, str) and self._is_nom_subtype(a_nom, b):
            return True

        # sequences relate pointwise; must come before the structural-equality fallback
        if isinstance(a, SequenceType) and isinstance(b, SequenceType):
            return len(a.items) == len(b.items) and all(self.is_subtype(x, y) for x, y in zip(a.items, b.items))

        if a_nom is not None and self._structural_nominal(b) is not None:
            if isinstance(a, (FunctionType, OverloadType)) and isinstance(b, (FunctionType, OverloadType)):
                return self.callable_subtype(a, b)
            return a == b

        if a_nom is not None or self._structural_nominal(b) is not None:
            # e.g. 'function' of? FunctionType, or FunctionType of? TypeParameterize
            return False

        ha, hb = _head_of(a), _head_of(b)
        pa, pb = _as_prim_head(ha), _as_prim_head(hb)
        args_a, args_b = _args_of(a), _args_of(b)

        if pa is None or pb is None:
            return a == b

        if not self._is_nom_subtype(pa, pb):
            return False

        if not args_b:
            # F<A> of? G  or  F of? G
            return True
        if not args_a:
            # F of? G<B> — open world
            return False
        if len(args_a) != len(args_b):
            return False

        # covariance
        return all(self.is_subtype(ai, bi) for ai, bi in zip(args_a, args_b))


    def _integer_literal_implies(self, literal: IntegerLiteralType, target: Primitive) -> bool:
        """Whether an exact integer value inhabits a nominal numeric target."""
        if integer_literal_fits(literal.value, target):
            return True
        return self._is_nom_subtype('int', target)

    def _string_literal_implies(
        self,
        literal: StringLiteralType,
        target: LiteralAtom,
    ) -> bool:
        """Whether an exact string can materialize in the requested domain."""

        byte_count, scalar_count, grapheme_count = string_literal_lengths(literal.value)
        if isinstance(target, StringLiteralType):
            return literal == target
        if isinstance(target, StringType):
            return target.length is None or target.length == grapheme_count
        if isinstance(target, ArrayType):
            lengths = {
                'uint8': byte_count,
                'uint32': scalar_count,
                'grapheme': grapheme_count,
                'char': grapheme_count,
                'string': grapheme_count,
            }
            length = lengths.get(target.element) if isinstance(target.element, str) else None
            return length is not None and (
                target.length is None or target.length == length
            )
        if isinstance(target, str):
            if target in {'char', 'grapheme'}:
                return grapheme_count == 1
            return self._is_nom_subtype('string', target)
        return False


    def _binary_literal_implies(
        self,
        literal: BinaryLiteralType,
        target: LiteralAtom,
    ) -> bool:
        """Whether exact binary data can materialize as a byte array."""

        if isinstance(target, BinaryLiteralType):
            return literal == target
        if target == TOP_TYPE:
            return True
        return (
            isinstance(target, ArrayType)
            and target.element == 'uint8'
            and (target.length is None or target.length == len(literal.value))
        )


    def _path_literal_implies(
        self,
        literal: PathLiteralType,
        target: LiteralAtom,
    ) -> bool:
        if isinstance(target, PathLiteralType):
            return literal == target
        if isinstance(target, PathType):
            return self._path_type_implies(literal, target)
        if isinstance(target, ObjectType):
            return self._path_type_implies(literal, target)
        return isinstance(target, str) and self._is_nom_subtype('object', target)


    def _path_type_implies(
        self,
        path: PathType,
        target: ObjectType,
    ) -> bool:
        if len(path.fields) != len(target.fields):
            return False
        return all(
            source.name == expected.name
            and source.mutable == expected.mutable
            and self.is_subtype(source.type, expected.type)
            for source, expected in zip(path.fields, target.fields)
        )


    def clause_is_empty(self, clause: DnfClause) -> bool:
        """
        Clause = P1 & P2 & … & ~N1 & ~N2 & …
        Empty iff the positive meet is uninhabited, or it is implied by some ~Ni
        (i.e. meet of? Ni).
        """
        pos = [atom for pol, atom in clause if pol]
        neg = [atom for pol, atom in clause if not pol]

        # reduce positives by successive meet
        meet: LiteralAtom | None
        if not pos:
            meet = TOP_TYPE  # only negatives: ~N1 & ~N2 & … usually non-empty
        else:
            meet = pos[0]
            for atom in pos[1:]:
                meet = self._meet_atoms(meet, atom)
                if meet is None:
                    return True

        if meet == BOTTOM_TYPE:
            return True

        # top with only negatives → non-empty (open world)
        if meet == TOP_TYPE:
            return False

        # P & ~N empty iff P of? N
        for n in neg:
            if self._atom_implies_atom(meet, n):
                return True

        return False


    def is_empty(self, t: TypeExpr) -> bool:
        """True iff t is uninhabited."""
        dnf = normalize(t)
        # prune as we go; all clauses empty => empty type
        return all(self.clause_is_empty(c) for c in dnf)




    ########################################################
    # Function Subtyping
    ########################################################


    def function_subtype(self, f: FunctionType, g: FunctionType) -> bool:
        """True if F is usable wherever G is expected (call-shape inclusion).

        Parameter types are contravariant; return type is covariant.
        Optional parameters on G cannot be required on F; F may add optional
        keyword-only extras.
        """
        if len(f.pos_or_kw) != len(g.pos_or_kw):
            return False
        for fp, gp in zip(f.pos_or_kw, g.pos_or_kw):
            if gp.name is not None and fp.name != gp.name:
                return False
            if fp.place != gp.place:
                return False
            if not gp.required and fp.required:
                return False
            if not self.is_subtype(gp.type, fp.type):
                return False

        f_kw = {k.name: k for k in f.kw_only}
        g_kw = {k.name: k for k in g.kw_only}
        g_pos_names = {p.name for p in g.pos_or_kw if p.name is not None}

        for name, gk in g_kw.items():
            fk = f_kw.get(name)
            if fk is not None:
                if fk.place != gk.place:
                    return False
                if not self.is_subtype(gk.type, fk.type):
                    return False
                if not gk.required and fk.required:
                    return False
                continue

            fp = next((p for p in f.pos_or_kw if p.name == name), None)
            if fp is not None:
                if fp.place != gk.place:
                    return False
                if not gk.required:
                    return False
                if not self.is_subtype(gk.type, fp.type):
                    return False
                continue

            if f.rest is not None:
                continue
            return False

        for fk in f.kw_only:
            if not fk.required:
                continue
            if fk.name in g_kw or fk.name in g_pos_names:
                continue
            return False

        return self.is_subtype(f.ret, g.ret)


    def callable_subtype(self, f: FunctionType | OverloadType, g: FunctionType | OverloadType) -> bool:
        """Overload coverage: every method in G is covered by some method in F."""
        fs = f.methods if isinstance(f, OverloadType) else [f]
        gs = g.methods if isinstance(g, OverloadType) else [g]
        return all(any(self.function_subtype(fm, gm) for fm in fs) for gm in gs)



    ########################################################
    # Dispatch System
    ########################################################

    def infer_type_args(
        self,
        m: FunctionType,
        pos_types: list[TypeExpr],
        kw_types: dict[str, TypeExpr],
        expected_return: TypeExpr | None = None,
    ) -> dict[str, TypeExpr] | None:
        """Bind generic params from arguments and an optional contextual return type."""
        type_vars = {gp.name for gp in m.type_params}
        bindings: dict[str, TypeExpr] = {}
        contextual_type_vars: set[str] = set()

        def bind_type_var(name: str, actual: TypeExpr) -> bool:
            if name not in bindings:
                bindings[name] = actual
                return True

            current = bindings[name]
            if name in contextual_type_vars:
                return self.is_subtype(actual, current)
            if current == actual:
                # `T` bound to the same singleton twice still names the operand
                # type, not the result: `1 + 1` is an `int`, not the singleton `1`
                if isinstance(current, IntegerLiteralType):
                    bindings[name] = 'int'
                elif isinstance(current, StringLiteralType):
                    bindings[name] = StringType()
                elif isinstance(current, BinaryLiteralType):
                    bindings[name] = ArrayType('uint8', len(current.value))
                return True
            if isinstance(current, IntegerLiteralType) and isinstance(actual, IntegerLiteralType):
                bindings[name] = 'int'
                return True
            if isinstance(current, StringLiteralType) and isinstance(actual, StringLiteralType):
                bindings[name] = StringType()
                return True
            if isinstance(current, BinaryLiteralType) and isinstance(actual, BinaryLiteralType):
                if len(current.value) != len(actual.value):
                    return False
                bindings[name] = ArrayType('uint8', len(current.value))
                return True
            if isinstance(current, IntegerLiteralType) and self.is_subtype(current, actual):
                bindings[name] = actual
                return True
            if isinstance(actual, IntegerLiteralType) and self.is_subtype(actual, current):
                return True
            if isinstance(current, StringLiteralType) and self.is_subtype(current, actual):
                bindings[name] = actual
                return True
            if isinstance(actual, StringLiteralType) and self.is_subtype(actual, current):
                return True
            if isinstance(current, BinaryLiteralType) and self.is_subtype(current, actual):
                bindings[name] = actual
                return True
            if isinstance(actual, BinaryLiteralType) and self.is_subtype(actual, current):
                return True
            promoted = self.promote_type(current, actual)
            if promoted is None:
                return False
            bindings[name] = promoted
            return True

        def match_param(param_t: TypeExpr, arg_t: TypeExpr) -> bool:
            # a type variable binds; structure around it is matched pointwise
            if isinstance(param_t, str) and param_t in type_vars:
                return bind_type_var(param_t, arg_t)
            if isinstance(param_t, TypeVariable) and param_t.name in type_vars:
                return bind_type_var(param_t.name, arg_t)
            if isinstance(param_t, RefinedType):
                return match_param(param_t.base, arg_t)
            if isinstance(param_t, ArrayType) and isinstance(arg_t, ArrayType):
                if param_t.length is not None and arg_t.length != param_t.length:
                    return False
                return match_param(param_t.element, arg_t.element)
            if isinstance(param_t, ObjectType) and isinstance(arg_t, ObjectType) and param_t.brand == arg_t.brand:
                if [f.name for f in param_t.fields] != [f.name for f in arg_t.fields]:
                    return False
                return all(match_param(pf.type, af.type) for pf, af in zip(param_t.fields, arg_t.fields))
            if isinstance(param_t, FunctionType) and isinstance(arg_t, FunctionType) and not param_t.type_params:
                if len(param_t.pos_or_kw) != len(arg_t.pos_or_kw):
                    return False
                return all(
                    match_param(pp.type, ap.type) for pp, ap in zip(param_t.pos_or_kw, arg_t.pos_or_kw)
                ) and match_param(param_t.ret, arg_t.ret)
            if isinstance(param_t, TypeOr) and not isinstance(arg_t, TypeOr):
                # `T | undefined` against `int64`: bind through the variable member
                variables = [
                    item for item in param_t.items
                    if (isinstance(item, TypeVariable) and item.name in type_vars) or (isinstance(item, str) and item in type_vars)
                ]
                others = [item for item in param_t.items if item not in variables]
                if len(variables) == 1 and not any(self.is_subtype(arg_t, other) for other in others):
                    return match_param(variables[0], arg_t)
            return self.is_subtype(arg_t, param_t)

        ret_var = m.ret.name if isinstance(m.ret, TypeVariable) else m.ret
        if expected_return is not None and isinstance(ret_var, str) and ret_var in type_vars:
            bindings[ret_var] = expected_return
            contextual_type_vars.add(ret_var)

        if len(pos_types) > len(m.pos_or_kw) and m.rest is None:
            return None

        for i, pt in enumerate(pos_types):
            if i < len(m.pos_or_kw) and not match_param(m.pos_or_kw[i].type, pt):
                return None

        pos_names = {p.name for p in m.pos_or_kw if p.name is not None}
        kw_map = {k.name: k for k in m.kw_only}

        for name, kt in kw_types.items():
            if name in pos_names:
                p = next(p for p in m.pos_or_kw if p.name == name)
                if m.pos_or_kw.index(p) < len(pos_types):
                    return None
                if not match_param(p.type, kt):
                    return None
                continue
            if name in kw_map:
                if not match_param(kw_map[name].type, kt):
                    return None
                continue
            if m.rest is None:
                return None

        if any(
            param.required and param.name not in kw_types
            for param in m.pos_or_kw[len(pos_types):]
        ):
            return None

        for k in m.kw_only:
            if k.required and k.name not in kw_types:
                return None

        for gp in m.type_params:
            if gp.name not in bindings:
                return None
            if not self.is_subtype(bindings[gp.name], gp.bound):
                return None

        return bindings

    def try_instantiate_for_call(
        self,
        m: FunctionType,
        pos_types: list[TypeExpr],
        kw_types: dict[str, TypeExpr],
        expected_return: TypeExpr | None = None,
    ) -> FunctionType | None:
        """Instantiate generics for this call (if any) and check concrete acceptance."""
        if not m.type_params:
            return m if self.call_accepted_concrete(m, pos_types, kw_types) else None
        bindings = self.infer_type_args(m, pos_types, kw_types, expected_return)
        if bindings is None:
            return None
        inst = instantiate_method(m, bindings)
        return inst if self.call_accepted_concrete(inst, pos_types, kw_types) else None

    def call_accepted_concrete(self, m: FunctionType, pos_types: list[TypeExpr], kw_types: dict[str, TypeExpr]) -> bool:
        """Whether a fully concrete method accepts this call (no free type params)."""
        if len(pos_types) > len(m.pos_or_kw) and m.rest is None:
            return False

        for i, pt in enumerate(pos_types):
            if i < len(m.pos_or_kw) and not self.is_subtype(pt, m.pos_or_kw[i].type):
                return False

        pos_names = {p.name for p in m.pos_or_kw if p.name is not None}
        kw_map = {k.name: k for k in m.kw_only}

        for name, kt in kw_types.items():
            if name in pos_names:
                p = next(p for p in m.pos_or_kw if p.name == name)
                if m.pos_or_kw.index(p) < len(pos_types):
                    return False
                if not self.is_subtype(kt, p.type):
                    return False
                continue
            if name in kw_map:
                if not self.is_subtype(kt, kw_map[name].type):
                    return False
                continue
            if m.rest is None:
                return False

        if any(
            param.required and param.name not in kw_types
            for param in m.pos_or_kw[len(pos_types):]
        ):
            return False

        for k in m.kw_only:
            if k.required and k.name not in kw_types:
                return False
        return True

    def call_accepted(self, m: FunctionType, pos_types: list[TypeExpr], kw_types: dict[str, TypeExpr]) -> bool:
        """Whether a single method accepts this call (instantiating generics if needed)."""
        return self.try_instantiate_for_call(m, pos_types, kw_types) is not None

    def applicable(
        self,
        methods: list[FunctionType],
        pos_types: list[TypeExpr],
        kw_types: dict[str, TypeExpr],
        expected_return: TypeExpr | None = None,
    ) -> list[FunctionType]:
        """Instantiated methods that accept the call-site argument types."""
        out: list[FunctionType] = []
        for m in methods:
            inst = self.try_instantiate_for_call(m, pos_types, kw_types, expected_return)
            if inst is not None:
                out.append(inst)
        return out

    def _applicable_indexed(
        self,
        methods: list[FunctionType],
        pos_types: list[TypeExpr],
        kw_types: dict[str, TypeExpr],
        expected_return: TypeExpr | None = None,
    ) -> list[tuple[int, FunctionType]]:
        """Applicable instantiated methods paired with their declaration index.

        Instantiation may create a new ``FunctionType``, so identity or
        structural equality cannot reliably recover the selected source
        alternative after dispatch. Preserving the original index gives HIR
        lowering an unambiguous link to that alternative.
        """
        out: list[tuple[int, FunctionType]] = []
        for index, method in enumerate(methods):
            inst = self.try_instantiate_for_call(method, pos_types, kw_types, expected_return)
            if inst is not None:
                out.append((index, inst))
        return out

    def more_specific(self, m1: FunctionType, m2: FunctionType) -> bool:
        """True if m1 is strictly more specific than m2 (positional params only)."""
        if len(m1.pos_or_kw) != len(m2.pos_or_kw):
            return False
        leq = all(self.is_subtype(a.type, b.type) for a, b in zip(m1.pos_or_kw, m2.pos_or_kw))
        geq = all(self.is_subtype(b.type, a.type) for a, b in zip(m1.pos_or_kw, m2.pos_or_kw))
        return leq and not geq

    def match_best_function(
        self,
        methods: list[FunctionType],
        pos_types: list[TypeExpr],
        kw_types: dict[str, TypeExpr] | None = None,
        expected_return: TypeExpr | None = None,
    ) -> DispatchResult:
        """Julia-style: unique most-specific applicable method, with promote-and-redispatch fallback."""
        kw_types = kw_types or {}
        apps = self._applicable_indexed(methods, pos_types, kw_types, expected_return)
        promote_pos: list[TypeExpr | None] = [None] * len(pos_types)

        if not apps and pos_types and all(isinstance(t, str) for t in pos_types):
            common: Primitive | None = pos_types[0]  # type: ignore[assignment]
            for t in pos_types[1:]:
                assert common is not None
                common = self.promote_type(common, t)
                if common is None:
                    break
            if common is not None:
                promoted_pos = [common] * len(pos_types)
                apps = self._applicable_indexed(methods, promoted_pos, kw_types, expected_return)
                if apps:
                    promote_pos = [None if t == common else common for t in pos_types]

        if not apps:
            raise DispatchError(f'no matching method for pos={pos_types!r} kw={kw_types!r}')
        winners = [
            (index, method)
            for index, method in apps
            if not any(
                self.more_specific(other, method)
                for other_index, other in apps
                if other_index != index
            )
        ]
        if len(winners) > 1:
            winners = self._prefer_exact_number_methods(winners, pos_types)
        if len(winners) != 1:
            raise DispatchError(f'ambiguous call among {len(apps)} applicable methods')
        method_index, method = winners[0]
        return DispatchResult(method, method_index, promote_pos)

    def _prefer_exact_number_methods(
        self,
        winners: list[tuple[int, FunctionType]],
        pos_types: list[TypeExpr],
    ) -> list[tuple[int, FunctionType]]:
        """Compile-time numbers pick exact (rational) parameters over fixed ones.

        A literal such as `45°` materializes into whichever representation the
        parameter wants, so it is applicable to both a `rational` and a `fixed`
        overload; the exact one wins.
        """
        def number_of(type_: TypeExpr) -> TypeExpr:
            return type_.number if isinstance(type_, QuantityType) else type_

        def preference(method: FunctionType) -> tuple[int, ...]:
            scores: list[int] = []
            for position, arg_type in enumerate(pos_types):
                if not isinstance(number_of(arg_type), (IntegerLiteralType, RationalLiteralType)):
                    continue
                if position >= len(method.pos_or_kw):
                    continue
                param = number_of(method.pos_or_kw[position].type)
                scores.append(2 if param == self.rational_object else 1 if param == self.fixed_object else 0)
            return tuple(scores)

        best = max(preference(method) for _, method in winners)
        return [(index, method) for index, method in winners if preference(method) == best]





# TODO: want an arbitrary DAG renderer. should draw dags with unicode box drawing characters, no repeated nodes




#######################################################################
# Nominal Type Hierarchy
#######################################################################




# Type algebra is driven by: is_subtype(t, target) => is_empty(t & ~target) for arbitrary type expressions t and target.

# TODO: type algebra/operations functions
# probably merge is_subtype and satisfies. Or make is_subtype a pure nominal subtype lookup
# `A of? B | C` => `(A of? B) or (A of? C)`
# `A of! B & C` => `(A of! B) and (A of! C)`
# `A of? not B` => `not (A of? B)`
# `A<B> of? C<D>` => `(A of? C) and (B of? D)`
# `A<B> of? C` => `A of? C`
# `A of? C<D>` => `(A of? C) and (T of? D)` (where any is the largest type that can parameterize `A`). I think typically this one will be false, so probably just short circuit for now
# `(A | B) of? C` => `(A of? C) and (B of? C)`
# `(A & B) of? C` => `(A of? C) or (B of? C)`  This one is a little weird. should it be `or`` or `and``


# A | B of? C | D => A of? (C | D) and B of? (C | D) => ((A of? C) or (A of? D)) and ((B of? C) or (B of? D))


#######################################################################
# Semantic Subtyping
# is_subtype(S, T)  ⟺  is_empty(S & ~T)
# TypeParameterize is covariant in all args.
#######################################################################


type LiteralAtom = Primitive | TypeParameterize | TypeVariable | DimensionType | QuantityType | FunctionType | OverloadType | SequenceType | IntegerLiteralType | RationalLiteralType | RefinedType | StringLiteralType | BinaryLiteralType | StringType | ArrayType | ObjectType | ModuleType | NamedType
# (is_positive, atom)
type DnfClause = tuple[tuple[bool, LiteralAtom], ...]
type Dnf = tuple[DnfClause, ...]  # () == never; ((),) == any (one empty clause)


# ---------------------------------------------------------------------------
# Smart constructors
# ---------------------------------------------------------------------------

def intersect(*xs: TypeExpr) -> TypeExpr:
    """Build the intersection of type expressions.

    Flattens nested TypeAnd nodes, drops duplicate members, and absorbs identities/annihilators:
    - `any` is dropped (T & any = T)
    - `never` short-circuits to `never` (T & never = never)
    - no conjuncts left → `any`; a single conjunct → that type alone
    """
    flat: list[TypeExpr] = []
    def add(x: TypeExpr) -> None:
        if x not in flat:
            flat.append(x)
    for x in xs:
        if x == TOP_TYPE:
            continue
        if x == BOTTOM_TYPE:
            return BOTTOM_TYPE
        if isinstance(x, TypeAnd):
            for item in x.items:
                add(item)
        else:
            add(x)
    if not flat:
        return TOP_TYPE
    if len(flat) == 1:
        return flat[0]
    return TypeAnd(flat)


def union(*xs: TypeExpr) -> TypeExpr:
    """Build the union of type expressions.

    Flattens nested TypeOr nodes, drops duplicate members, and absorbs identities/annihilators:
    - `never` is dropped (T | never = T)
    - `any` short-circuits to `any` (T | any = any)
    - no disjuncts left → `never`; a single disjunct → that type alone
    """
    flat: list[TypeExpr] = []
    def add(x: TypeExpr) -> None:
        if x not in flat:
            flat.append(x)
    for x in xs:
        if x == BOTTOM_TYPE:
            continue
        if x == TOP_TYPE:
            return TOP_TYPE
        if isinstance(x, TypeOr):
            for item in x.items:
                add(item)
        else:
            add(x)
    if not flat:
        return BOTTOM_TYPE
    if len(flat) == 1:
        return flat[0]
    return TypeOr(flat)


def sequence(*items: TypeExpr) -> Type:
    """Collapse expressed-value types: 0 items -> void, 1 -> that item, n -> SequenceType.

    Nested SequenceTypes are flattened since () groups are non-semantic: `(1 (2 3))` expresses
    three values. Flattening applies only to sequences — a generator<...> value is one value.
    """
    flat: list[TypeExpr] = []
    for x in items:
        if isinstance(x, SequenceType):
            flat.extend(x.items)
        else:
            flat.append(x)
    if not flat:
        return VOID_TYPE
    if len(flat) == 1:
        return flat[0]
    return SequenceType(flat)


# ---------------------------------------------------------------------------
# Negation → NNF (Not only on atoms)
# ---------------------------------------------------------------------------

def negate(t: TypeExpr) -> TypeExpr:
    if t == TOP_TYPE:
        return BOTTOM_TYPE
    if t == BOTTOM_TYPE:
        return TOP_TYPE
    if isinstance(t, TypeNot):
        return to_nnf(t.type)
    if isinstance(t, TypeOr):
        return intersect(*(negate(x) for x in t.items))
    if isinstance(t, TypeAnd):
        return union(*(negate(x) for x in t.items))
    # Primitive | TypeParameterize | FunctionType | OverloadType: keep as Not(atom).
    # Do NOT push not into TypeParameterize args or function signatures.
    return TypeNot(t)


def to_nnf(t: TypeExpr) -> TypeExpr:
    if isinstance(t, TypeNot):
        return negate(t.type)
    if isinstance(t, TypeOr):
        return union(*(to_nnf(x) for x in t.items))
    if isinstance(t, TypeAnd):
        return intersect(*(to_nnf(x) for x in t.items))
    if isinstance(t, TypeParameterize):
        return TypeParameterize(to_nnf(t.t), [to_nnf(a) for a in t.args])
    if isinstance(t, TypeVariable):
        return t
    if isinstance(t, SequenceType):
        return SequenceType([to_nnf(x) for x in t.items])
    if isinstance(t, ArrayType):
        return ArrayType(to_nnf(t.element), t.length)
    if isinstance(t, QuantityType):
        return QuantityType(to_nnf(t.number), t.dimension)
    if isinstance(t, DimensionType):
        return t
    if isinstance(t, StringType):
        return t
    if isinstance(t, (PathType, PathLiteralType)):
        return t
    if isinstance(t, ObjectType):
        return ObjectType(
            tuple(
                ObjectField(field.name, to_nnf(field.type), field.mutable)
                for field in t.fields
            ),
            t.brand,
        )
    if isinstance(t, ModuleType):
        return t
    return t  # Primitive | TypeFunc | TypeOverload | top | bottom


# ---------------------------------------------------------------------------
# Normalize → DNF of signed atoms
# ---------------------------------------------------------------------------

def normalize(t: TypeExpr) -> Dnf:
    return _dnf(to_nnf(t))


def _dnf(t: TypeExpr) -> Dnf:
    if t == BOTTOM_TYPE:
        return ()
    if t == TOP_TYPE:
        return ((),)  # true
    if isinstance(t, TypeNot):
        # NNF: inner is atom
        return (((False, t.type),),)
    if isinstance(t, (str, TypeParameterize, TypeVariable, DimensionType, QuantityType, FunctionType, OverloadType, SequenceType, IntegerLiteralType, RationalLiteralType, RefinedType, StringLiteralType, BinaryLiteralType, StringType, ArrayType, ObjectType, PathType, PathLiteralType, ModuleType, NamedType)):
        return (((True, t),),)
    if isinstance(t, TypeOr):
        clauses: list[DnfClause] = []
        for x in t.items:
            clauses.extend(_dnf(x))
        return tuple(clauses)
    if isinstance(t, TypeAnd):
        acc: Dnf = ((),)
        for x in t.items:
            acc = _distribute(acc, _dnf(x))
        return acc
    raise TypeError(f'normalize: unhandled {t!r}')


def _distribute(left: Dnf, right: Dnf) -> Dnf:
    if not left or not right:
        return ()
    out: list[DnfClause] = []
    for a in left:
        for b in right:
            out.append(a + b)
    return tuple(out)





# ---------------------------------------------------------------------------
# Constructor heads + covariant TypeParam
# ---------------------------------------------------------------------------

def _head_of(atom: LiteralAtom) -> TypeExpr:
    return atom.t if isinstance(atom, TypeParameterize) else atom


def _args_of(atom: LiteralAtom) -> list[TypeExpr]:
    return list(atom.args) if isinstance(atom, TypeParameterize) else []


def _as_prim_head(head: TypeExpr) -> Primitive | None:
    """v1: constructor heads are primitives (array, dict, …)."""
    return head if isinstance(head, str) else None




# ---------------------------------------------------------------------------
# Function types: call-shape subtyping
# ---------------------------------------------------------------------------

# def _methods_of(t: FunctionType | OverloadType) -> list[FunctionType]:
#     return t.methods if isinstance(t, OverloadType) else [t]


# def overload_function(a: FunctionType | OverloadType, b: FunctionType | OverloadType) -> OverloadType:
#     """
#     Create an instance of an overloaded function

#     ```dewy
#     let f = (a:int) => {...}
#     let g = (a:string) => {...}
#     let h = f & g
    
#     h(1)       # calls f
#     h"hello"   # calls g
#     ```

#     > NOTE: this is only meant for combining functions. Other interpretations of the same operators (bitwise, logical, type intersection, etc.) are handled elsewhere.
#     """
#     return OverloadType(_methods_of(a) + _methods_of(b))




class DispatchError(ValueError):
    """No unique most-specific applicable method."""


@dataclass
class DispatchResult:
    """Dispatch winner, its source-list index, and required argument promotions.

    ``method`` may be a freshly instantiated generic signature. The stable
    ``method_index`` therefore provides the semantic-to-HIR link to the
    original alternative.
    """

    method: FunctionType
    method_index: int
    promote_pos: list[TypeExpr | None]  # parallel to call pos_types; None = no promote


def substitute_type(t: TypeExpr, bindings: dict[str, TypeExpr]) -> TypeExpr:
    """Replace free type-param names in a type expression."""
    if isinstance(t, str):
        return bindings.get(t, t)
    if isinstance(t, TypeVariable):
        return bindings.get(t.name, t)
    if isinstance(t, IntegerLiteralType):
        return t
    if isinstance(t, RationalLiteralType):
        return t
    if isinstance(t, RefinedType):
        return RefinedType(substitute_type(t.base, bindings), t.propositions)
    if isinstance(t, (StringLiteralType, BinaryLiteralType, StringType, DimensionType, PathType, PathLiteralType, ModuleType, NamedType)):
        return t
    if isinstance(t, QuantityType):
        return QuantityType(substitute_type(t.number, bindings), t.dimension)
    if isinstance(t, ArrayType):
        return ArrayType(substitute_type(t.element, bindings), t.length)
    if isinstance(t, ObjectType):
        return ObjectType(
            tuple(
                ObjectField(
                    field.name,
                    substitute_type(field.type, bindings),
                    field.mutable,
                )
                for field in t.fields
            ),
            t.brand,
        )
    if isinstance(t, TypeAnd):
        return TypeAnd([substitute_type(x, bindings) for x in t.items])
    if isinstance(t, TypeOr):
        return TypeOr([substitute_type(x, bindings) for x in t.items])
    if isinstance(t, TypeNot):
        return TypeNot(substitute_type(t.type, bindings))
    if isinstance(t, TypeParameterize):
        return TypeParameterize(substitute_type(t.t, bindings), [substitute_type(a, bindings) for a in t.args])
    if isinstance(t, SequenceType):
        return SequenceType([substitute_type(x, bindings) for x in t.items])
    if isinstance(t, FunctionType):
        nested_shadow = {gp.name for gp in t.type_params}
        inner = {k: v for k, v in bindings.items() if k not in nested_shadow}
        return FunctionType(
            [
                PosOrKwArg(
                    p.name,
                    substitute_type(p.type, inner),
                    p.required,
                    p.place,
                )
                for p in t.pos_or_kw
            ],
            [
                KwOnlyArg(
                    k.name,
                    substitute_type(k.type, inner),
                    k.required,
                    k.place,
                )
                for k in t.kw_only
            ],
            t.rest,
            substitute_type(t.ret, inner),
            list(t.type_params),
        )
    if isinstance(t, OverloadType):
        methods: list[FunctionType] = []
        for m in t.methods:
            sm = substitute_type(m, bindings)
            assert isinstance(sm, FunctionType)
            methods.append(sm)
        return OverloadType(methods)
    raise TypeError(f'substitute_type: unhandled {t!r}')


def instantiate_method(m: FunctionType, type_args: dict[str, TypeExpr]) -> FunctionType:
    """Substitute generic type params, returning a concrete FunctionType."""
    if not m.type_params:
        return m
    return FunctionType(
        [
            PosOrKwArg(
                p.name,
                substitute_type(p.type, type_args),
                p.required,
                p.place,
            )
            for p in m.pos_or_kw
        ],
        [
            KwOnlyArg(
                k.name,
                substitute_type(k.type, type_args),
                k.required,
                k.place,
            )
            for k in m.kw_only
        ],
        m.rest,
        substitute_type(m.ret, type_args),
        [],
    )





# TODO: this will be handled by the dispatch system
# # TODO: come up with canonical names for each operator (e.g. division/mod)
# system_binops: list[tuple[str, TypeExpr, TypeExpr]] = [
#     ('__add__', 'number', 'number'),      #TODO: type here should be anything that is ring or group or ...
#     ('__sub__', 'number', 'number'),
#     ('__mul__', 'number', 'number'),
#     ('__idiv__', 'number', 'number'),
#     ('__mod__', 'number', 'number'),
#     ('__tdiv__', 'number', 'number'),
#     ('__pow__', 'number', 'number'),
   
#     # Don't worry about these for now...    
#     # ('__lshift__', 'int', 'int'),
#     # ('__rshift__', 'int', 'int'),
#     # ('__lrotate__', 'int', 'int'),
#     # ('__rrotate__', 'int', 'int'),
    
#     # ('__eq__', 'any', 'any'),
#     # ('__neq__', 'any', 'any'),
#     # # ('__gt__', 'comparable', 'comparable'),   #TODO: type here is anything that is partial orderable... but also have to be comparable to its own type...
#     # # ('__lt__', 'comparable', 'comparable'),   #      basically what would our notation for traits on generic types be?   <T>   T<traits=comparable>
#     # # ('__gte__', 'comparable', 'comparable'),
#     # # ('__lte__', 'comparable', 'comparable'),   __gt__ = <T has PartialOrder>(left:T right:T):>bool => ...

#     # ('__is__', 'any', 'type'),
#     # ('__isnt__', 'any', 'type'),


#     # TODO: what about iterators  e.g. `x in X and y in Y`
#     ('__and__', 'bool', 'bool'),
#     ('__or__', 'bool', 'bool'),
#     ('__nand__', 'bool', 'bool'),
#     ('__nor__', 'bool', 'bool'),
#     ('__xor__', 'bool', 'bool'),
#     ('__xnor__', 'bool', 'bool'),
# ]
