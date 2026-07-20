"""
HIR 

The richest AST representation containing all the high level features in the language represented as distinct AST nodes

TODO: 
Features (i.e. each should probably get an AST node)
(a lot of stuff could probably be pulled from syntax.py)
- strings
- string interpolations
- numbers
- arrays/dicts/objects
- ranges
- complex ranges, multiple spans, etc.
- iterators
- logically combined iterators
- type system stuff? I think type-checking should be complete at this point
- 


perhaps after this phase theres a second typechecking phase making use of all the rich type information built at this phase?
"""

from dataclasses import dataclass
from typing import Literal
from ..parser import t0
from ..reporting import Span
from . import ty

# Type: TypeAlias = ty.TypeExpr

@dataclass
class AST:
    loc: Span
    type: ty.Type # All ASTs have a type. typechecking involves propogating the type upward through expressions

@dataclass
class Void(AST): ...

@dataclass 
class Return(AST):
    item: AST|None = None


@dataclass
class Declare(AST):
    decltype: Literal['let', 'const'] # others tbd
    name: str                         #TBD future handling of unpacking assignment
    type: ty.Type
    expr: AST

@dataclass
class ExpressedIdentifier(AST):
    name: str

@dataclass
class Bool(AST):
    value: bool

@dataclass
class Integer(AST):
    prefix: t0.BasePrefix
    value: int


@dataclass
class String(AST):
    content: str


@dataclass
class Param:
    name: str  #TODO: list/dict/obj unpack might go here too? also multi-arg collections could go here
    type: ty.Type

@dataclass
class BoundParam(Param):
    value: AST

@dataclass
class FunctionLiteral(AST):
    pos_or_kw_args: list[Param]  # all `default` should be None...
    kw_only_args: list[Param|BoundParam]
    rest_args: Param | BoundParam | None
    rettype: ty.Type
    body: AST

#TODO: partial eval is basically like a stack of function calls (though need to be careful about eager vs lazy evaluation of parameters (since they probably should be eager))


"""
syntax for various types of function signature arguments:


# ─── DECLARATION ────────────────────────────────────────────────────────
# No position-only args: every parameter is always addressable by name,
# which is what keeps partial-eval-by-name working everywhere.

let F = (

    # positional-or-keyword, required. may be passed by position or by name.
    a b c

    # a bound arg (has a default) drops OUT of the positional running, so it
    # becomes keyword-only automatically. placement is free: `d` sits between
    # positional-or-keyword args but is skipped by positional calls.
    #   F(1 2 3)      -> a=1 b=2 c=3, d defaulted
    #   F(1 2 3 d=9)  -> d overridden by name
    a b d=10 c        # (same idea, just showing default interleaved is fine)

    # destructure a single positional aggregate. polymorphic on the caller:
    #   caller passes an array  -> bound by ORDER (names free, order matters)
    #   caller passes an object -> bound by NAME  (names must match, order free)
    # untyped like this is ALLOWED but UNIDIOMATIC; emits a
    # "array-vs-object is caller-determined" warning at this definition.
    [p q r]

    # pin it to object form with an annotation -> no warning; a caller that
    # passes an array (or wrong field names) is an error.
    [m n]:[m:int n:string]
    # (pinning to array form uses its array type annotation)
    [s t u]:<string int bool>
    [v w x]:[int int int]
    [y z ...inner_rest]:array<int>

    # the divider. positionals are closed here; everything after is
    # required keyword-only. use bare `...` when you want the boundary
    # WITHOUT collecting anything.
    ...
    flag
    mode

):>T => { ... }



# ─── CAPTURE + DELEGATION ───────────────────────────────────────────────
# `...rest` captures every leftover arg (positional AND keyword) that didn't
# match a declared param. it's an opaque bundle: you forward it, you
# never read it. it also serves as the positional/keyword divider, so any
# bare param after it is keyword-only.

let wrapper = (a b ...rest opts=false) => {
    # peel-and-forward: intercept what you name, forward the rest to ONE callee.
    F(a b)
    G(...rest)
}

# broadcast: forward the same bundle to MULTIPLE callees.
# legal iff every callee accepts ALL of rest:  row(rest) ⊆ params(F) ∩ params(G)
# (partitioning rest between callees is intentionally NOT supported — that
#  would require naming the split, so just name it in the signature instead.)
let tee = (...rest) => {
    F(...rest)
    G(...rest)
}

# partial application via `@`: produce the function-value without firing it.
let configured = @F(x=10 ...rest)
#   - rest carries a field not in F   -> compile-time error (row ⊄ params(F))
#   - rest fills every remaining slot -> fine; result is a fully-bound value,
#     still re-bindable by name:   let tweaked = @configured(a=99)






misc note: making generic is basically the same as making a scope to declare the thing in:
```
let F = <T of number U V>(a:T b:T u:U v:V):>T => {...}
let F = {
    let T:type = generic_param(root=number)
    let U:type = generic_param()
    let V:type = generic_param()
    (a:T b:T u:U v:V):>T => {...}
}
```

"""

@dataclass
class FunctionCall(AST):
    pos_args: list[AST]
    kw_args: dict[str, AST]
    #TODO: spread args


# TODO:perhaps we can make the call dataclass even more uniform here... 
# e.g. dealing with named vs positional vs unpack vs collect vs etc. args
# TODO: also `func` might not be an identifier... might be a func literal, opfn etc.
# @dataclass
# class Call(AST):
#     func: Identifier #|FunctionLiteral
#     args: list[AST] #TODO: named args, partial eval, etc.

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