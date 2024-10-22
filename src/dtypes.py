from .syntax import AST, Type, TypeParam, And, Or, Not

from typing import Protocol, TypeVar

import pdb

class Literal(AST):
    value: AST
    def __str__(self) -> str:
        return f'{self.value}'

class TBD(AST):
    """For representing values where the type is underconstrained"""
    def __str__(self) -> str:
        return '<TBD>'

class Fail(AST):
    """For representing values that typechecking fails on"""
    reason: str|None = None
    def __str__(self) -> str:
        return '<Fail>'


class TypeofFunc(Protocol):
    def __call__(self, ast: AST) -> Type: ...


def identity(ast: AST) -> Type:
    return Type(type(ast))

def get_typeof_fn_map() -> dict[type[AST], TypeofFunc]:
    pdb.set_trace()
    return {
    }




TypeExpr = Type | And | Or | Not | Literal | TBD | Fail
def typeof(ast: AST) -> TypeExpr:
    """Basically like evaluate, but just returns the type information. Doesn't actually evaluate the AST"""
    pdb.set_trace()
    ...


# def promote/coerce() -> Type: #or make_compatible
# promotion_table = {...}
# type_tree = {...}