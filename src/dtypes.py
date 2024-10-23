from dataclasses import dataclass, field
from functools import cache
from typing import Protocol, TypeVar, Generator, Sequence, cast, overload, Literal as TypingLiteral
from enum import Enum, auto


from .syntax import (
    AST,
    Type,
    PointsTo, BidirPointsTo,
    ListOfASTs, PrototypeTuple, Block, Array, Group, Range, ObjectLiteral, Dict, BidirDict, UnpackTarget,
    PrototypeIdentifier, TypedIdentifier,
    Void, void, Undefined, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    Identifier, Express, Declare,
    PrototypePyAction, PrototypeFunctionLiteral, Call, Access,
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
                Type(PrototypePyAction),
                PrototypePyAction(
                    Group([Assign(TypedIdentifier(Identifier('s'), Type('string')), String(''))]),
                    Type(Void)
                )
            ),
            'print': Scope._var(
                DeclarationType.CONST,
                Type(PrototypePyAction),
                PrototypePyAction(
                    Group([Assign(TypedIdentifier(Identifier('s'), Type('string')), String(''))]),
                    Type(Void)
                )
            ),
            'readl': Scope._var(
                DeclarationType.CONST,
                Type(PrototypePyAction),
                PrototypePyAction(
                    Group([]),
                    Type(String)
                )
            )
        })


class TypeofFunc(Protocol):
    def __call__(self, ast: AST, scope: Scope, params:bool=False) -> TypeExpr:
        """
        Return the type of the given AST node.

        Args:
            ast (AST): the AST node to determine the type of
            scope (Scope): the scope in which the AST node is being evaluated
            params (bool, optional): indicates if full type checking including parameterization should be done. Defaults to False.

        Returns:
            Type: the type of the AST node
        """

def identity(ast: AST, scope: Scope, params:bool=False) -> Type:
    return Type(type(ast))

def short_circuit(ret: type[AST], param_fallback:TypeofFunc|None=None) -> TypeofFunc:
    def inner(ast: AST, scope: Scope, params:bool=False) -> Type:
        if params and param_fallback is not None:
            return param_fallback(ast, scope, params)
        return Type(ret)
    return inner

def cannot_typeof(ast: AST, scope: Scope, params:bool=False):
    raise ValueError(f'INTERNAL ERROR: determining the type of `({type(ast)}) {ast}` is not possible')


@cache
def get_typeof_fn_map() -> dict[type[AST], TypeofFunc]:
    return {
        Declare: short_circuit(Void),
        # Call: typeof_call,
        # Block: typeof_block,
        # Group: typeof_group,
        Array: typeof_array,
        # Dict: typeof_dict,
        # PointsTo: typeof_points_to,
        # BidirDict: typeof_bidir_dict,
        # BidirPointsTo: typeof_bidir_points_to,
        # ObjectLiteral: typeof_object_literal,
        # # Object: no_op,
        # Access: typeof_access,
        Assign: short_circuit(Void),
        # IterIn: typeof_iter_in,
        PrototypeFunctionLiteral: short_circuit(PrototypeFunctionLiteral),
        # FunctionLiteral: typeof_function_literal,
        # # Closure: typeof_closure,
        # # PyAction: typeof_pyaction,
        String: identity,
        IString: short_circuit(String),
        PrototypeIdentifier: typeof_identifier,
        Identifier: typeof_identifier,
        Express: typeof_express,
        Int: identity,
        # # Float: no_op,
        Bool: identity,
        # Range: no_op,
        CycleLeft: lambda ast, scope, params: typeof(ast.operand, scope, params),
        CycleRight: lambda ast, scope, params: typeof(ast.operand, scope, params),
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
        AtHandle: typeof_at_handle,
        Undefined: identity,
        Void: identity,
        #TODO: other AST types here
    }



def typeof(ast: AST, scope: Scope, params:bool=False) -> TypeExpr:
    """Basically like evaluate, but just returns the type information. Doesn't actually evaluate the AST"""
    typeof_fn_map = get_typeof_fn_map()

    ast_type = type(ast)
    if ast_type in typeof_fn_map:
        return typeof_fn_map[ast_type](ast, scope, params)

    pdb.set_trace()
    raise NotImplementedError(f'typeof not implemented for {ast_type}')


# def promote/coerce() -> Type: #or make_compatible
# promotion_table = {...}
# type_tree = {...}

# def typecheck/validate()



class JuxtaposeCase(Enum):
    """Useful for cases where a boolean answer isn't rich enough"""
    callable = auto()
    indexable = auto()
    other = auto()



def disambiguate_juxtapose(ast:AST, scope:Scope) -> JuxtaposeCase:
    """
    Determine if the given AST is callable, indexable, or something else
    This way we can determine which type of juxtapose and thus which precedence to use
    """
    t = typeof(ast, scope)
    if isinstance(t, Type):
        if t.t is Array:
            return JuxtaposeCase.indexable
        elif t.t in (PrototypePyAction, PrototypeFunctionLiteral):
            return JuxtaposeCase.callable
        else:
            return JuxtaposeCase.other

    if isinstance(t, And):
        pdb.set_trace()
        ...

    if isinstance(t, Or):
        pdb.set_trace()
        ...

    if isinstance(t, Not):
        pdb.set_trace()
        ...

    if isinstance(t, Literal):
        pdb.set_trace()
        ...

    if isinstance(t, TBD):
        pdb.set_trace()
        ...

    if isinstance(t, Fail):
        pdb.set_trace()
        ...

    pdb.set_trace()
    ...

# def is_callable(ast:AST, scope: Scope) -> Answer:
#     t = typeof(ast, scope)
#     pdb.set_trace()

    # match ast:
    #     # ASTs the have to be evaluated to determine the type
    #     case PrototypeIdentifier(name):
    #         pdb.set_trace()
    #         #TODO: use full type checker here to determine the type
    #         # DEBUG: for now, hardcode to call
    #         return True
    #     #TODO: any other types that need to be evaluated to determine if callable
    #     case Access(right=PrototypeIdentifier()) | Access(right=AtHandle(operand=PrototypeIdentifier())):
    #         pdb.set_trace()
    #         #TODO: same deal as above. for debugging, hardcode to call
    #         return True

    #     # known callable ASTs
    #     case PrototypePyAction() | PrototypeFunctionLiteral():
    #         return True

    #     #TODO: may change this in the future, but for now, assume at handle can only be used on callables 
    #     #      as in when doing partial evaluation
    #     case AtHandle():
    #         pdb.set_trace()
    #         return True

    #     # known non-callables
    #     case Int() | String() | Bool(): #TODO: rest of them..
    #         return False

    #     # recuse into other ASTs
    #     # TODO: need to handle more cases for group. e.g. it could have multiple items that are void, but still only return a single AST
    #     #       and then also if there are multiple non-void items that makes a generator, which I think is not callable
    #     case Group(items):
    #         if len(items) == 0: return False #TODO: this generally shouldn't be possible as this should parse to a void literal
    #         if len(items) == 1: return is_callable(items[0], scope)
    #         pdb.set_trace()
    #         raise NotImplementedError(f"ERROR: unhandled case to check if is_callable: {ast=}")
    #         types = [get_type(i, scope) for i in items]
    #         types = [*filter(lambda t: t is not void, types)]
    #         if len(types) == 0: return False # this is possible if all items evaluate to void
    #         if len(types) == 1: return is_callable_type(types[0])
    #         if len(types) > 1: return False

    #     case _:
    #         raise ValueError(f"ERROR: unhandled case to check if is_callable: {ast=}")

    # pdb.set_trace()

# def is_indexable(ast:AST, scope: Scope):
#     t = typeof(ast, scope)
#     pdb.set_trace()
#     raise NotImplementedError


def typeof_identifier(ast: PrototypeIdentifier|Identifier, scope: Scope, params:bool=False) -> TypeExpr:
    var = scope.get(ast.name)
    if var is None:
        raise KeyError(f'variable "{ast.name}" not found in scope')
    if var.type is not untyped:
        return var.type

    return typeof(var.value, scope, params)


def typeof_at_handle(ast: AtHandle, scope: Scope, params:bool=False) -> Type:
    raise NotImplementedError('typeof_at_handle not implemented')

def typeof_express(ast: Express, scope: Scope, params:bool=False) -> Type:
    raise NotImplementedError('typeof_express not implemented')

def typeof_array(ast: Array, scope: Scope, params:bool=False) -> Type:
    if not params:
        return Type(Array)