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
from ..reporting import Span
from . import ty

# Type: TypeAlias = ty.TypeExpr

@dataclass
class AST:
    span: Span
    type: ty.Type # All ASTs have a type. typechecking involves propogating the type upward through expressions


# BinaryOperator: TypeAlias = Literal['']

# @dataclass
# class BinOp(AST):
#     op: BinaryOperator
#     left: AST
#     right: AST


"""
primary language types to make hir nodes from:
- undefined
- void
- untyped
- noreturn
- extern
- intrinsic
- new
- end
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
- assign (runtime or comptile bool flag)
- binop
- prefix op
- postfix op
- suppress
- 
"""