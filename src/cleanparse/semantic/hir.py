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
class Identifier(AST):
    name: str

@dataclass
class Bool(AST):
    value: bool

# @dataclass
# class Int(AST):
#     # prefix: 
#     value: int

@dataclass
class String(AST):
    content: str


# TODO:perhaps we can make the call dataclass even more uniform here... 
# e.g. dealing with named vs positional vs unpack vs collect vs etc. args
# TODO: also `func` might not be an identifier... might be a func literal, opfn etc.
@dataclass
class Call(AST):
    func: Identifier #|FunctionLiteral
    args: list[AST] #TODO: named args, partial eval, etc.

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