"""
HIR 

The richest AST representation containing all the high level features in the language represented as distinct AST nodes

TODO: 
Features (i.e. each should probably get an AST node)
(a lot of stuff could probably be pulled from syntax.py)
- strings
- string interpolations
- numbers
- dicts/objects
- ranges
- complex ranges, multiple spans, etc.
- iterators
- logically combined iterators
- type system stuff? I think type-checking should be complete at this point
- 


perhaps after this phase theres a second typechecking phase making use of all the rich type information built at this phase?
"""

from dataclasses import dataclass, field
from typing import Literal
from ..parser import t0
from ..reporting import Span
from . import ty

# Type: TypeAlias = ty.TypeExpr

@dataclass
class AST:
    loc: Span
    type: ty.Type # All ASTs have a type. typechecking involves propogating the type upward through expressions

    def __repr__(self) -> str:
        from .hir_display import hir_to_tree_str
        return hir_to_tree_str(self)

    def __str__(self) -> str:
        from .hir_display import hir_to_dewy
        return hir_to_dewy(self)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # @dataclass would otherwise generate a field repr that hides these.
        cls.__repr__ = AST.__repr__  # type: ignore[method-assign]
        cls.__str__ = AST.__str__  # type: ignore[method-assign]

@dataclass
class Void(AST): ...


@dataclass
class Suppress(AST):
    """Evaluate ``item`` for its effects without expressing its value."""

    item: AST


@dataclass
class Undefined(AST):
    """The first-class singleton value denoting absence."""


@dataclass
class Return(AST):
    item: AST|None = None


@dataclass
class IfArm(AST):
    """One boolean conditional arm in an ordered flow chain."""

    condition: AST
    body: AST


@dataclass
class LoopArm(AST):
    """One loop arm whose condition is boolean or a stateful iterator."""

    condition: AST
    body: AST


@dataclass
class Flow(AST):
    """An ordered `if`/`loop` chain with an optional final default body."""

    arms: list[IfArm | LoopArm]
    default: AST | None = None


@dataclass
class ScopeMetatag(AST):
    """A generic metatag declared throughout its containing lexical scope."""

    name: str = ''


@dataclass
class Break(AST):
    """Exit an enclosing loop, optionally selected through a scope metatag."""

    label: str | None = None
    loop_levels: int = 0


@dataclass
class Continue(AST):
    """Continue an enclosing loop, optionally selected through a scope metatag."""

    label: str | None = None
    loop_levels: int = 0


@dataclass
class ShortCircuit(AST):
    """A lazy boolean logical operator selected through operator dispatch."""

    op: Literal['and', 'or', 'nand', 'nor']
    left: AST
    right: AST


@dataclass
class TypeTest(AST):
    """A runtime `is?` or `isnt?` test against a type expression."""

    value: AST
    test_type: ty.TypeExpr
    negated: bool


@dataclass
class Declare(AST):
    decltype: Literal['let', 'const'] # others tbd
    name: str                         #TBD future handling of unpacking assignment
    annotation: ty.Type | None        # explicit `:T` on the binding, if any; AST.type is still void
    expr: AST
    binding_id: int | None = field(default=None, kw_only=True)

@dataclass
class ExpressedIdentifier(AST):
    name: str
    binding_id: int | None = field(default=None, kw_only=True)


@dataclass
class Place(AST):
    """A mutable binding or projected field/index passed by reference with ``@``."""

    target: ExpressedIdentifier | MemberAccess | Index


@dataclass
class Assign(AST):
    """Assignment statement; compound operators remain explicit until MIR lowering."""
    target: ExpressedIdentifier
    op: str
    value: AST


@dataclass
class Bool(AST):
    value: bool

@dataclass
class Integer(AST):
    prefix: t0.BasePrefix
    value: int


@dataclass
class ArrayLiteral(AST):
    """A one-dimensional homogeneous array value."""

    items: list[AST]


@dataclass
class ObjectField:
    """One initialized field of an object literal."""

    loc: Span
    name: str
    value: AST
    binding_id: int | None = None
    mutable: bool = True


@dataclass
class ObjectLiteral(AST):
    """A structural object value with source-order fields."""

    fields: list[ObjectField]


@dataclass
class MemberAccess(AST):
    """A named field read from an object."""

    value: AST
    name: str
    mutable: bool = True


@dataclass
class MemberAssign(AST):
    """Mutation of one object field."""

    target: MemberAccess
    value: AST


@dataclass
class TypeValue(AST):
    """A compile-time type used as a named alias."""

    value: ty.TypeAliasValue


@dataclass
class ModuleNamespace(AST):
    """A compile-time namespace for one imported source module."""

    name: str


@dataclass
class ArrayLength(AST):
    """The element count of an array value."""

    array: AST


@dataclass
class DictLookup(AST):
    """``d[key]`` on a dictionary: ``V | undefined`` by linear search over the
    hidden key array, reading the matching value."""

    keys: AST
    values: AST
    key: AST


@dataclass
class DictStore(AST):
    """``d[key] = value``: replace the value of an existing key, else append
    the entry (insertion order is the entry order)."""

    keys: AST
    values: AST
    key: AST
    value: AST


@dataclass
class DictContains(AST):
    """``key in? d`` on a dictionary."""

    keys: AST
    key: AST


@dataclass
class ArrayMethod(AST):
    """A compiler-provided method bound to a named array binding.

    ``type`` is the method's FunctionType; calling it mutates the receiver in
    place (``push``, ``pop``, ``clear``, ``reserve``), as if ``array`` were a
    Dewy object type defining these methods.
    """

    array: AST
    name: str


@dataclass
class IteratorExpression(AST):
    """A scoped `name in iterable` expression advanced by an enclosing loop."""

    target: ExpressedIdentifier
    iterable: AST
    first: int
    step: int
    last: int | None
    count: int | None


IteratorLogicalOp = Literal['and', 'or', 'xor', 'nand', 'nor', 'xnor']
IteratorFormulaToken = int | IteratorLogicalOp


@dataclass
class MultiIteratorExpression(AST):
    """Eager iterator leaves and a postfix logical formula over their indices."""

    iterators: list[IteratorExpression]
    formula: list[IteratorFormulaToken]
    repeats_when_exhausted: bool


@dataclass
class Index(AST):
    """A scalar array read validated by the semantic bounds pass."""

    array: AST
    index: AST
    constant_index: int | None


@dataclass
class IndexAssign(AST):
    """Mutation of one statically proven array element."""

    target: Index
    value: AST


@dataclass
class String(AST):
    content: str


@dataclass
class InterpolatedString(AST):
    """A source string whose expression fields have been typechecked.

    The node is a semantic value, but targets may specialize consumers such as
    ``print`` without first materializing one contiguous runtime string.
    """

    parts: list[AST]


@dataclass
class BasedString(AST):
    prefix: t0.BasePrefix
    digits: str
    content: bytes


@dataclass
class StringLength(AST):
    string: AST


@dataclass
class StringIndex(AST):
    string: AST
    index: AST
    constant_index: int | None


@dataclass
class StringSlice(AST):
    string: AST
    range: Range


@dataclass
class StringEqual(AST):
    left: AST
    right: AST
    negated: bool = False


@dataclass
class StringConcat(AST):
    left: AST
    right: AST


@dataclass
class ValueCast(AST):
    """Value cast: explicit `expr as Target`, or an implicit promotion. `type` is the target."""
    expr: AST


@dataclass
class RepresentationCast(AST):
    """A conversion that materializes a value in a different representation."""

    expr: AST


@dataclass
class Transmute(AST):
    """Bit-preserving reinterpretation. `type` is the target type."""
    expr: AST


@dataclass
class Param:
    name: str  #TODO: list/dict/obj unpack might go here too? also multi-arg collections could go here
    type: ty.Type
    binding_id: int | None = field(default=None, kw_only=True)
    position_only: bool = field(default=False, kw_only=True)
    place: bool = field(default=False, kw_only=True)

    def __repr__(self) -> str:
        from .hir_display import hir_to_tree_str
        return hir_to_tree_str(self)

    def __str__(self) -> str:
        from .hir_display import hir_to_dewy
        return hir_to_dewy(self)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__repr__ = Param.__repr__  # type: ignore[method-assign]
        cls.__str__ = Param.__str__  # type: ignore[method-assign]

@dataclass
class BoundParam(Param):
    value: AST

@dataclass
class FunctionLiteral(AST):
    pos_or_kw_args: list[Param|BoundParam]
    kw_only_args: list[Param|BoundParam]
    rest_args: Param | BoundParam | None
    rettype: ty.Type
    body: AST
    object_receiver: bool = False
    object_fields: tuple[tuple[int, str], ...] = ()
    object_type: ty.ObjectType | None = None

# TODO: Partial evaluation is roughly a stack of function calls. Explicitly
# supplied values are evaluated and saved immediately; signature defaults stay
# as per-call fallbacks until a completed call needs them.

@dataclass
class OverloadedFunction(AST):
    """A callable value formed by combining callable operands with `&`."""
    alternates: list[AST]


"""
Function signature and call-binding design
==========================================

Required parameters before `...` are positional-or-keyword. Call arguments
are processed from left to right:

1. A positional argument binds the first parameter still available by
   position.
2. A named argument binds the parameter with that name and removes it from
   the remaining positional sequence.
3. One call cannot supply the same parameter twice.

For example:

    let combine = (a b=10 c) => [a b c]

    combine(1 2 3)       # a=1, b=2,  c=3
    combine(1 c=3)       # a=1, b=10, c=3
    combine(b=2 1 3)     # b=2, then a=1 and c=3
    combine(1 3)         # error: a=1, b=3, required c is missing

A signature default is a per-call fallback. It does not bind the parameter
when the function is defined, and it does not remove that parameter's
positional slot. A normal call evaluates the default separately if the
parameter is still unset after all explicit arguments have been processed.
This gives mutable defaults a fresh value for each call.

Partial evaluation uses the same argument-ordering rule, but an explicitly
supplied value is evaluated and saved when the `@function(...)` expression is
evaluated. That parameter then leaves the resulting function's positional
sequence. Its name remains available for a later explicit replacement.
Defaults that have not been needed yet remain per-call fallbacks rather than
being evaluated during partial evaluation.

    let configured = @combine(b=20)  # 20 is evaluated and saved now
    configured(1 3)                  # a=1, b=20, c=3
    configured(1 3 b=30)             # explicitly replaces saved b

A bare `...` closes the positional sequence without collecting arguments.
Parameters after it are keyword-only: those without defaults are required,
while those with defaults are optional.

    let render = (value ... width:int64 theme="light") => {...}
    render(text width=80)

The planned `...rest` form both closes the positional sequence and captures
otherwise unmatched positional and named arguments. The captured arguments
form an opaque bundle intended for forwarding, not direct inspection.

    let wrapper = (a b ...rest trace=false) => {
        log(trace)
        target(a b ...rest)
    }

Forwarding the same bundle to more than one function is valid only when every
destination accepts every captured argument. Dewy deliberately does not split
one captured bundle among several destinations; arguments that need different
destinations should be named explicitly in the wrapper signature.

Source signatures require local names for all parameters. Because parameter
names and type names are both ordinary identifiers, a bare identifier is
always a parameter name rather than an unnamed type annotation. Wrapping one
parameter in `<>` makes it position-only:

    let increment = (<value:int64>) => value + 1

Here `value` is available in the body but callers cannot write `value=...`.
The same required, annotated, and defaulted parameter forms work inside `<>`;
only their availability by name at the call site changes.

Destructured parameters are also planned. An unannotated `[a b c]` parameter
could accept an array by position or an object by field name; an explicit
annotation removes that ambiguity:

    [a b]:[a:int b:string]       # object fields matched by name
    [a b]:<int string>           # fixed sequence matched by position
    [a b ...items]:array<int>    # array prefix plus remaining elements

Generic parameters can be understood as declarations in a scope surrounding
the function signature and body:

    let F = <T of number U V>(a:T b:T u:U v:V):>T => {...}

is conceptually equivalent to:

    let F = {
        let T:type = generic_param(root=number)
        let U:type = generic_param()
        let V:type = generic_param()
        (a:T b:T u:U v:V):>T => {...}
    }
"""

@dataclass
class FunctionCall(AST):
    """A checked call to a function value or overload set.

    ``selected_method_index`` is populated only when ``func`` has
    ``OverloadType``. It indexes the original ordered method set, allowing
    target lowering to select the matching concrete function without repeating
    generic instantiation or dispatch.
    """

    func: AST
    pos_args: list[AST]
    kw_args: dict[str, AST]
    selected_method_index: int | None = None
    #TODO: spread args

@dataclass
class Partial(AST):
    ... # TODO

@dataclass
class Block(AST):
    items: list[AST]
    scoped: bool


@dataclass
class TypeBlock(AST):
    items: list[AST]


@dataclass
class Range(AST):
    bounds: Literal['[]', '[)', '(]', '()'] | None  #none means the range hasn't been wrapped, so bounds are assumed []
    step_pair: tuple[AST, AST] | None
    left: AST | None
    right: AST | None


@dataclass
class RangeMembership(AST):
    """A runtime membership test, optionally with a normalized static step."""

    value: AST
    range: Range
    first: int | None = None
    step: int | None = None
    last: int | None = None
    count: int | None = None



"""
primary language types to make hir nodes from:
[named literals]
- undefined
- void
- untyped
- noreturn
- extern
- intrinsic
- new
- end

[primitives]
- bool
- int
- rational
- float
- string
- istring
- ellipsis

[type expressions]
- range<T> start, end, step. can we use generics to make inner elements have the same type?
- iterator
- iterator expression
- function
- array
- dict
- bidict
- object
- type block
- parameterization
- generic declaration
- expression sequence...
- unpack
- collect
- flow
- if
- loop
- (match) ... tbd
- assignment (`=` or `::` runtime or comptile bool flag)
- declare (`let` or `const`, `:=`)
- binop
- prefix op
- postfix op
- suppress
"""
