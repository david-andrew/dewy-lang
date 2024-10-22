from dataclasses import dataclass, field
from functools import cache
from typing import Protocol, TypeVar, Generator, Sequence, cast, overload, Literal as TypingLiteral


from .syntax import (
    AST,
    Type,
    PointsTo, BidirPointsTo,
    ListOfASTs, PrototypeTuple, Block, Array, Group, Range, ObjectLiteral, Dict, BidirDict, UnpackTarget,
    TypedIdentifier,
    Void, void, Undefined, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    Identifier, Express, Declare,
    PrototypePyAction, Call, Access,
    Assign,
    Int, Bool,
    Range, IterIn,
    BinOp,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    UnaryPrefixOp, UnaryPostfixOp,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv, AtHandle,
    CycleLeft, CycleRight, Suppress,
    BroadcastOp,
    CollectInto, SpreadOutFrom,
    DeclarationType,
)
from .postparse import FunctionLiteral, Signature



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

TypeExpr = Type | And | Or | Not | Literal | TBD | Fail

class TypeofFunc(Protocol):
    def __call__(self, ast: AST, scope: 'Scope') -> Type: ...


def identity(ast: AST, scope: 'Scope') -> Type:
    return Type(type(ast))

def short_circuit(ret: type[AST]) -> TypeofFunc:
    def inner(ast: AST, scope: Scope) -> Type:
        return Type(ret)

def cannot_typeof(ast: AST, scope: 'Scope') -> AST:
    raise ValueError(f'INTERNAL ERROR: determining the type of `({type(ast)}) {ast}` is not possible')


@cache
def get_typeof_fn_map() -> dict[type[AST], TypeofFunc]:
    return {
        Declare: short_circuit(Void),
        # Call: typeof_call,
        # Block: typeof_block,
        # Group: typeof_group,
        # Array: typeof_array,
        # Dict: typeof_dict,
        # PointsTo: typeof_points_to,
        # BidirDict: typeof_bidir_dict,
        # BidirPointsTo: typeof_bidir_points_to,
        # ObjectLiteral: typeof_object_literal,
        # # Object: no_op,
        # Access: typeof_access,
        Assign: short_circuit(Void),
        # IterIn: typeof_iter_in,
        # FunctionLiteral: typeof_function_literal,
        # # Closure: typeof_closure,
        # # PyAction: typeof_pyaction,
        String: identity,
        IString: short_circuit(String),
        Identifier: cannot_typeof,
        # Express: typeof_express,
        Int: identity,
        # # Float: no_op,
        Bool: identity,
        # Range: no_op,
        CycleLeft: lambda ast, scope: typeof(ast.operand),
        CycleRight: lambda ast, scope: typeof(ast.operand),
        # Flow: typeof_flow,
        # Default: typeof_default,
        # If: typeof_if,
        # Loop: typeof_loop,
        # UnaryPos: typeof_unary_dispatch,
        # UnaryNeg: typeof_unary_dispatch,
        # UnaryMul: typeof_unary_dispatch,
        # UnaryDiv: typeof_unary_dispatch,
        # Not: typeof_unary_dispatch,
        Greater: short_circuit(Bool),
        GreaterEqual: short_circuit(Bool),
        Less: short_circuit(Bool),
        LessEqual: short_circuit(Bool),
        Equal: short_circuit(Bool),
        # And: typeof_binary_dispatch,
        # Or: typeof_binary_dispatch,
        # Xor: typeof_binary_dispatch,
        # Nand: typeof_binary_dispatch,
        # Nor: typeof_binary_dispatch,
        # Xnor: typeof_binary_dispatch,
        # Add: typeof_binary_dispatch,
        # Sub: typeof_binary_dispatch,
        # Mul: typeof_binary_dispatch,
        # Div: typeof_binary_dispatch,
        # Mod: typeof_binary_dispatch,
        # Pow: typeof_binary_dispatch,
        # AtHandle: typeof_at_handle,
        Undefined: identity,
        Void: identity,
        #TODO: other AST types here
    }




def typeof(ast: AST, scope: 'Scope') -> TypeExpr:
    """Basically like evaluate, but just returns the type information. Doesn't actually evaluate the AST"""
    typeof_fn_map = get_typeof_fn_map()

    ast_type = type(ast)
    if ast_type in typeof_fn_map:
        return typeof_fn_map[ast_type](ast, scope)

    raise NotImplementedError(f'evaluation not implemented for {ast_type}')


# def promote/coerce() -> Type: #or make_compatible
# promotion_table = {...}
# type_tree = {...}




# Scope class only used during parsing to keep track of callables
@dataclass
class Scope:
    @dataclass
    class _var():
        # name:str #name is stored in the dict key
        decltype: DeclarationType
        type: TypeExpr
        value: AST

    parent: 'Scope | None' = None
    # callables: dict[str, AST | None] = field(default_factory=dict) #TODO: maybe replace str->AST with str->signature (where signature might be constructed based on the func structure)
    vars: 'dict[str, Scope._var]' = field(default_factory=dict)

    @overload
    def get(self, name:str, throw:TypingLiteral[True]=True, search_parents:bool=True) -> 'Scope._var': ...
    @overload
    def get(self, name:str, throw:TypingLiteral[False], search_parents:bool=True) -> 'Scope._var|None': ...
    def get(self, name:str, throw:bool=True, search_parents:bool=True) -> 'Scope._var|None':
        for s in self:
            if name in s.vars:
                return s.vars[name]
            if not search_parents:
                break

        if throw:
            raise KeyError(f'variable "{name}" not found in scope')
        return None

    def assign(self, name:str, value:AST):
        assert len(DeclarationType.__members__) == 2, f'expected only 2 declaration types: let, const. found {DeclarationType.__members__}'

        # var is already declared in current scope
        if name in self.vars:
            var = self.vars[name]
            assert var.decltype != DeclarationType.CONST, f"Attempted to assign to constant variable: {name=}{var=}. {value=}"
            var.value = value
            return

        var = self.get(name, throw=False)

        # var is not declared in any scope
        if var is None:
            self.let(name, value, untyped)
            return

        # var was declared in a parent scope
        if var.decltype == DeclarationType.LET:
            var.value = value
            return

        raise ValueError(f'Attempted to assign to constant variable: {name=}{var=}. {value=}')

    def declare(self, name:str, value:AST, type:Type, decltype:DeclarationType):
        if name in self.vars:
            var = self.vars[name]
            assert var.decltype != DeclarationType.CONST, f"Attempted to {decltype.name.lower()} declare a value that is const in this current scope. {name=}{var=}. {value=}"

        self.vars[name] = Scope._var(decltype, type, value)

    def let(self, name:str, value:AST, type:Type):
        self.declare(name, value, type, DeclarationType.LET)

    def const(self, name:str, value:AST, type:Type):
        self.declare(name, value, type, DeclarationType.CONST)

    def __iter__(self) -> Generator['Scope', None, None]:
        """return an iterator that walks up each successive parent scope. Starts with self"""
        s = self
        while s is not None:
            yield s
            s = s.parent

    #TODO: these should actually be defined in python.py. There should maybe only be stubs here..
    @classmethod
    def default(cls: type['Scope']) -> 'Scope':
        return cls(vars={
            'printl': Scope._var(
                DeclarationType.CONST,
                Type('callable'),
                PrototypePyAction(
                    Group([Assign(TypedIdentifier(Identifier('s'), Type('string')), String(''))]),
                    Type(Void)
                )
            ),
            'print': Scope._var(
                DeclarationType.CONST,
                Type('callable'),
                PrototypePyAction(
                    Group([Assign(TypedIdentifier(Identifier('s'), Type('string')), String(''))]),
                    Type(Void)
                )
            ),
            'readl': Scope._var(
                DeclarationType.CONST,
                Type('callable'),
                PrototypePyAction(
                    Group([]),
                    Type(String)
                )
            )
        })

