from .syntax import AST, Type, TypeParam, And, Or, Not

import pdb

class Literal(AST):
    value: AST
    def __str__(self) -> str:
        return f'{self.value}'

TypeExpr = Type | And | Or | Not | Literal

def typeof(ast: AST) -> TypeExpr:
    """Basically like evaluate, but just returns the type information. Doesn't actually evaluate the AST"""
    pdb.set_trace()
    ...