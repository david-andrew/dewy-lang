from dataclasses import dataclass, field
from functools import cache
from typing import Protocol, TypeVar, Generator, Sequence, Any, cast, overload, Literal as TypingLiteral
from collections import defaultdict
from types import SimpleNamespace

from .syntax import (
    AST,
    Type, TypeParam,
    PointsTo, BidirPointsTo,
    ListOfASTs, Block, Array, Group, Range, ObjectLiteral, Dict, BidirDict, UnpackTarget,
    TypedIdentifier, ReturnTyped,
    Void, void, Undefined, undefined, untyped, New, End, Extern, Intrinsic, Ellipsis,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    Identifier, Express, Declare,
    PrototypeBuiltin, Call, Access, Index,
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
from .parser import QJux
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

TypeExpr = Type | And | Or | Not | Literal | TBD | Fail | ReturnTyped


# TODO: consider moving metanamespace stuff into e.g. a utils/etc. file
class MetaNamespace(SimpleNamespace):
    """A simple namespace for storing AST meta attributes for use at runtime"""
    def __getattribute__(self, key: str) -> Any | None:
        """Get the attribute associated with the key, or None if it doesn't exist"""
        try:
            return super().__getattribute__(key)
        except AttributeError:
            return None

    def __setattr__(self, key: str, value: Any) -> None:
        """Set the attribute associated with the key"""
        super().__setattr__(key, value)



def ast_to_key(ast: AST) -> str:
    """Convert an AST to a key for use in a dictionary. Note: relies on ASTs class and memory address"""
    assert isinstance(ast, AST), f'ast_to_key only works on ASTs. {ast=}'
    return f'::{ast.__class__.__name__}@{hex(id(ast))}'

class MetaNamespaceDict(defaultdict):
    """A defaultdict that preprocesses AST keys to use the classname + memory address as the key"""
    def __init__(self):
        super().__init__(MetaNamespace)

    # add preprocessing to both __getitem__ and __setitem__ to handle AST keys
    # apparently __setitem__ always calls __getitem__ so we only need to override __getitem__
    def __getitem__(self, item: AST) -> Any | None:
        return super().__getitem__(ast_to_key(item))

T = TypeVar('T')
from typing import Generic
class ASTDict(dict[AST, T], Generic[T]):
    """A dict that preprocesses AST keys to use the classname + memory address as the key"""
    def __getitem__(self, item: AST) -> T:
        return super().__getitem__(ast_to_key(item))
    def __setitem__(self, item: AST, value: T) -> None:
        super().__setitem__(ast_to_key(item), value)
    def __delitem__(self, item: AST) -> None:
        super().__delitem__(ast_to_key(item))
    def __contains__(self, item: AST) -> bool:
        return super().__contains__(ast_to_key(item))
    def get(self, item: AST, default: T | None = None) -> T | None:
        return super().get(ast_to_key(item), default)


# Scope class only used during parsing to keep track of callables
@dataclass
class Scope:
    @dataclass
    class _var():
        # name:str #name is stored in the dict key
        decltype: DeclarationType
        type: TypeExpr
        value: AST

        def __repr__(self) -> str:
            """Overwrite __repr__ so that we can format value with more compact __str__ rather than __repr__"""
            return f'Scope._var(decltype={self.decltype!r}, type={self.type!r}, value={self.value})'

    parent: 'Scope | None' = None
    # callables: dict[str, AST | None] = field(default_factory=dict) #TODO: maybe replace str->AST with str->signature (where signature might be constructed based on the func structure)
    vars: 'dict[str, Scope._var]' = field(default_factory=dict)
    meta: dict[AST, MetaNamespace] = field(default_factory=MetaNamespaceDict)

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

        # cannot assign with void
        assert value is not void, f"Attempted to assign void value to variable: {name=}. {value=}"

        # var is already declared in current scope
        if name in self.vars:
            var = self.vars[name]
            assert var.decltype != DeclarationType.CONST or var.value is void, f"Attempted to assign to constant variable: {name=}. {var=}. {value=}"
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

        # TODO: this strip group thing is a hack
        #       need a more robust way to drill down to the actual type
        self.vars[name] = Scope._var(decltype, strip_group(type), value)

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

    def __repr__(self):
        return f'<Scope@{hex(id(self))}>'



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

class TypeofCallFunc(Protocol):
    def __call__(self, call: AST, args: AST|None, scope: Scope, params:bool=False):
        """
        Return the type that results from calling the given AST node.

        Args:
            call (AST): the AST node to determine the type of
            args (AST|None): the arguments to the call. None means call with no args
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


_external_typeof_fn_map: dict[type[AST], TypeofFunc] = {}
# TODO: would be cool if this could be a decorator (that figured out the type from the first arg)
def register_typeof(cls: type[AST], fn: TypeofFunc):
    _external_typeof_fn_map[cls] = fn

_external_typeof_call_fn_map: dict[type[AST], TypeofCallFunc] = {}
# TODO: would be cool if this could be a decorator (that figured out the type from the first arg)
def register_typeof_call(cls: type[AST], fn: TypeofCallFunc):
    _external_typeof_call_fn_map[cls] = fn

@cache
def get_typeof_fn_map() -> dict[type[AST], TypeofFunc]:
    return {
        Declare: short_circuit(Void),
        Call: typeof_call,
        Block: typeof_block,
        Group: typeof_group,
        Array: typeof_array,
        # Dict: typeof_dict,
        # PointsTo: typeof_points_to,
        # BidirDict: typeof_bidir_dict,
        # BidirPointsTo: typeof_bidir_points_to,
        # ObjectLiteral: typeof_object_literal,
        # # Object: no_op,
        Access: typeof_access,
        Assign: short_circuit(Void),
        IterIn: short_circuit(Bool), #typeof_iter_in,
        FunctionLiteral: short_circuit(FunctionLiteral), # typeof_function_literal, #TODO: long term should probably return the signature
        # # Closure: typeof_closure,
        # # Builtin: typeof_builtin,
        String: identity,
        IString: short_circuit(String),
        Identifier: typeof_identifier,
        Express: typeof_express,
        Int: identity,
        # # Float: no_op,
        Bool: identity,
        Range: identity,
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
        And: typeof_logical_binop,
        Or: typeof_logical_binop,
        Xor: typeof_logical_binop,
        Nand: typeof_logical_binop,
        Nor: typeof_logical_binop,
        Xnor: typeof_logical_binop,
        Not: lambda ast, scope, params: typeof(ast.operand, scope, params),
        Add: typeof_binary_dispatch,
        Sub: typeof_binary_dispatch,
        Mul: typeof_binary_dispatch,
        Div: typeof_binary_dispatch,
        IDiv: typeof_binary_dispatch,
        Mod: typeof_binary_dispatch,
        Pow: typeof_binary_dispatch,
        LeftShift: typeof_binary_dispatch,
        RightShift: typeof_binary_dispatch,
        # LeftRotate: typeof_binary_dispatch,
        # RightRotate: typeof_binary_dispatch,
        AtHandle: typeof_at_handle,
        Undefined: identity,
        Void: identity,
        #TODO: other AST types here
    } | _external_typeof_fn_map



def typeof(ast: AST, scope: Scope, params:bool=False) -> TypeExpr:
    """Basically like evaluate, but just returns the type information. Doesn't actually evaluate the AST"""
    typeof_fn_map = get_typeof_fn_map()

    ast_type = type(ast)
    if ast_type in typeof_fn_map:
        return typeof_fn_map[ast_type](ast, scope, params)

    pdb.set_trace()
    raise NotImplementedError(f'typeof not implemented for {ast_type}')


# TODO: split resolution and typechecking into separate functions
#       resolution first, then typechecking since typechecking is hard when there are QASTs
def top_level_typecheck_and_resolve(ast: AST, scope: Scope) -> tuple[AST, ASTDict[Scope]]:
    group = Group([ast])
    gen = group.__iter_asts__(visit_replacement=True)
    scope_map: ASTDict[Scope] = ASTDict()
    scope_map[group] = scope
    inner_typecheck_and_resolve(group, gen, scope_map)

    return group.items[0], scope_map


def inner_typecheck_and_resolve(parent: AST, gen: Generator[AST, AST, None], scope_map: ASTDict[Scope]):

    for ast in gen:
        # if the specific AST has a scope, use it, otherwise use the parent's scope
        # then ensure all ASTs processed have a scope
        scope = scope_map.get(ast) or scope_map[parent]
        scope_map[ast] = scope

        match ast:
            case Void(): ...
            case Identifier(): ...
            case TypedIdentifier():
                ...
                #TODO: some contexts we do declare, and some we don't. i.e. in a function declaration/signatureS, we don't declare
                # scope.declare(ast.id.name, void, ast.type, DeclarationType.LET)
            case Express(): ...
            case Signature(): ...
            case Declare(decltype=decltype, target=target):
                # TODO: check that the type is valid if present...
                # declare the variable in the scope...
                match target:
                    case Identifier(name=name):
                        scope.declare(name, void, untyped, decltype)
                    case TypedIdentifier(name=name, type=type):
                        scope.declare(name, void, type, decltype)
                    # case ReturnTyped(left=left, right=right): ... # TODO
                    case UnpackTarget(target=target): pdb.set_trace(); ...
                    case Assign(left=left):
                        if isinstance(left, Identifier):
                            scope.declare(left.name, void, untyped, decltype) # note the assignment is handled by the child. We just declare the variable here
                        elif isinstance(left, TypedIdentifier):
                            scope.declare(left.id.name, void, left.type, decltype)
                        else:
                            pdb.set_trace()
                            raise NotImplementedError('Declare not implemented for target Assign with non-Identifier left side')
                    case _:
                        raise TypeError(f'INTERNAL ERROR: Declare received unexpected typeof target: {target}.')

            case Assign(left=left, right=right):
                if isinstance(left, Identifier):
                    scope.assign(left.name, right)
                elif isinstance(left, TypedIdentifier):
                    #TODO: check that the right is of the type of the left
                    scope.declare(left.id.name, right, left.type, DeclarationType.LET)
                else:
                    pdb.set_trace()
                    raise NotImplementedError('Assign not implemented for non-Identifier or TypedIdentifier left side')
                # # TODO: handling  other assignment targets on the left...

            case Group(items=items): ...

            case Block(items=items):
                # make a new layer to the scope, and assign it to all the children
                inner_scope = Scope(scope)
                for item in items:
                    scope_map[item] = inner_scope

            case FunctionLiteral(): ...

            case QJux(call=call, mul=mul, index=index):
                # print(f'visiting QJux {ast}')
                valid_branches = []
                if call is not None and is_call_valid(call, scope):
                    valid_branches.append(call)
                if index is not None and is_index_valid(index, scope):
                    valid_branches.append(index)
                if mul is not None and is_multiply_valid(mul, scope):
                    valid_branches.append(mul)
                if len(valid_branches) == 0:
                    raise ValueError(f'ERROR: no valid branches for QJux. must have at exactly one. {ast=}')
                if len(valid_branches) > 1:
                    raise ValueError(f'ERROR: multiple valid branches for QJux. must have exactly one. {ast=}')

                # overwrite QJux with the valid branch. Then continue so we process the replacement before going to the children
                valid_branch, = valid_branches
                gen.send(valid_branch)
                continue

                # pdb.set_trace()
                # ...
                # return valid_branches[0], scope
            case Call(f=f, args=args):
                # TODO: check if the signature of f agrees with the args...
                # print(f'skipping function typechecking...')
                ...

            case Access(left=left, right=right):
                # TODO: check that the member accessed exists on the left ast
                ...

            case Suppress(operand=operand): ... #generally suppress shouldn't care about the inner types

            case Int() | String() | IString() | Bool(): ...

            case And() | Or() | Xor() | Nand() | Nor() | Xnor() | Not():
                # TODO: check that the left and right are either int or bool
                ...
            case Greater() | GreaterEqual() | Less() | LessEqual() | Equal():# | NotEqual():
                # TODO: verify that the left and right are the comparable types (can compare with each other)
                ...

            case Add() | Sub() | Mul() | Div() | IDiv() | Mod() | LeftShift() | RightShift() | LeftRotate() | RightRotate():
                # TODO: verify left and right are compatible with the given operation
                ...

            case UnaryNeg() | UnaryPos() | UnaryMul() | UnaryDiv():
                # TODO: verify the operand is compatible with the unary operation
                ...

            case LeftShift() | RightShift() | LeftRotate() | RightRotate():
                # TODO: verify the left operand is shiftable and the right operand is an int
                ...

            case Flow() | If() | Loop() | Default():
                #TODO: verify that condition is a boolean
                ...

            case IterIn():
                # tbd if any type checking needed here.. probably not
                ...

            case Range():
                # TODO: check that the range bounds/step are valid
                ...

            case Type():
                # TODO: probably will use this somewhere...
                ...
            
            case ReturnTyped():
                # if not isinstance(parent, Type):
                #     gen.send(Type(ast))
                    # continue # TBD, probably do need to check the children...
                # pdb.set_trace()
                ... # TBD if any checking happens here vs where the thing is actually declared/used

            case AtHandle(operand=operand): ... #longer term, @handle should check that the inner thing can be referenced, and the type of the reference makes sense...

            # keyword singleton expressions
            case Ellipsis() | Undefined() | New() | End() | Extern() | Intrinsic(): ... # | Void() #TBD if void can pass here...

            case _:
                pdb.set_trace()
                ...
                raise ValueError(f'INTERNAL ERROR: typecheck_and_resolve not implemented for {type(ast)}')

        child_gen = ast.__iter_asts__(visit_replacement=True)
        inner_typecheck_and_resolve(ast, child_gen, scope_map)



# def typecheck_and_resolve(ast: AST, scope: Scope) -> AST | None:
#     match ast:
#         # TODO: all cases here
#         case _: ...

# def top_level_typecheck_and_resolve(root: AST, scope: Scope) -> tuple[AST, Scope]:
#     ast = Group([ast])
#     gen = ast.__iter_asts__()
#     return typecheck_and_resolve_v2(ast, gen, scope)

# def typecheck_and_resolve_v2(ast: AST, gen: Generator[AST, AST, None], scope: Scope) -> tuple[AST, Scope]:
#     match ast:
#         case Void(): ...
#             # return ast, scope
#         case Identifier(): ... # TODO...
#         case Express(): ...
#         case Signature(): ...
#         case Declare():
#             # TODO: check that the type is valid if present...
#             ...
#         case Assign(left=left, right=right):
#             if isinstance(left, Identifier):
#                 scope.assign(left.name, right)
#             else:
#                 pdb.set_trace()
#                 raise NotImplementedError('Assign not implemented for non-Identifier left side')
#             # TODO: put the identifier into the scope with the type of the right...
#             ...

#             # # TODO: handling identifier or other assignment targets on the left...
#             # typecheck_and_resolve(ast.right, scope)
#             # return ast, scope
#         case Group(items=items): ...
#             # pdb.set_trace()
#             # ...
#             # results = []
#             # for item in items:
#             #     result = typecheck_and_resolve(item, scope)
#             #     results.append(result)
#             # pdb.set_trace()
#             # ...
#         case Block(items=items):
#             # TODO: make a new layer to the scope
#             ...
#         case FunctionLiteral(): ...
#             # typecheck_and_resolve(ast.body, scope)
#             # return ast, scope
#         case QJux(call=call, mul=mul, index=index):
#             # print(f'visiting QJux {ast}')
#             valid_branches = []
#             if call is not None and is_call_valid(call, scope):
#                 valid_branches.append(call)
#             if index is not None and is_index_valid(index, scope):
#                 valid_branches.append(index)
#             if mul is not None and is_multiply_valid(mul, scope):
#                 valid_branches.append(mul)
#             if len(valid_branches) == 0:
#                 raise ValueError(f'ERROR: no valid branches for QJux. must have at exactly one. {ast=}')
#             if len(valid_branches) > 1:
#                 raise ValueError(f'ERROR: multiple valid branches for QJux. must have exactly one. {ast=}')

#             # overwrite QJux with the valid branch
#             valid_branch, = valid_branches
#             # typecheck_and_resolve(valid_branch, scope) #manually typechecking here since current __full_traversal_iter doesn't recurse into newly sent children... consider adjusting
#             gen.send(valid_branch)

#             # pdb.set_trace()
#             # ...
#             # return valid_branches[0], scope
#         case Call(f=f, args=args):
#             # TODO: check if the signature of f agrees with the args...
#             # print(f'skipping function typechecking...')
#             ...

#         case Int(): ...

#         case _:
#             pdb.set_trace()
#             ...
#             raise ValueError(f'INTERNAL ERROR: typecheck_and_resolve not implemented for {type(ast)}')


#     for child in (gen:=ast.__iter_asts__()):
#         typecheck_and_resolve(child, gen, scope)
#     pdb.set_trace()

# # def promote/coerce() -> Type: #or make_compatible
# # promotion_table = {...}
# # type_tree = {...}
# # TODO: perhaps ctx should be a dataclass that contains scope but also any other context needed? TBD...
# def typecheck_and_resolve(ast: AST, scope: Scope, ctx=None) -> tuple[AST, Scope]:
#     """Typecheck the given AST, and resolve any quantum ASTs to concrete selections based on the types"""
#     # ctx_stack: list[Literal['assigning', 'etc']] = []
#     # scope_stack = [scope]
#     # def pre_effect():
#     #     nonlocal scope, scope_stack
#     #     scope_stack.append(scope)
#     # def post_effect():
#     #     nonlocal scope, scope_stack
#     #     scope = scope_stack.pop()

#     ast = Group([ast])
#     for i in (gen := ast.__full_traversal_iter__(visit_replacement=True)):#pre_effect=pre_effect, post_effect=post_effect)):

#         print(f'visiting {i}')
#         match i:
#             case Void(): ...
#                 # return ast, scope
#             case Identifier(): ... # TODO...
#             case Express(): ...
#             case Signature(): ...
#             case Declare():
#                 # TODO: check that the type is valid if present...
#                 ...
#             case Assign(left=left, right=right):
#                 if isinstance(left, Identifier):
#                     scope.assign(left.name, right)
#                 else:
#                     pdb.set_trace()
#                     raise NotImplementedError('Assign not implemented for non-Identifier left side')
#                 # TODO: put the identifier into the scope with the type of the right...
#                 ...

#                 # # TODO: handling identifier or other assignment targets on the left...
#                 # typecheck_and_resolve(ast.right, scope)
#                 # return ast, scope
#             case Group(items=items): ...
#                 # pdb.set_trace()
#                 # ...
#                 # results = []
#                 # for item in items:
#                 #     result = typecheck_and_resolve(item, scope)
#                 #     results.append(result)
#                 # pdb.set_trace()
#                 # ...
#             case Block(items=items):
#                 # TODO: make a new layer to the scope
#                 ...
#             case FunctionLiteral(): ...
#                 # typecheck_and_resolve(ast.body, scope)
#                 # return ast, scope
#             case QJux(call=call, mul=mul, index=index):
#                 # print(f'visiting QJux {ast}')
#                 valid_branches = []
#                 if call is not None and is_call_valid(call, scope):
#                     valid_branches.append(call)
#                 if index is not None and is_index_valid(index, scope):
#                     valid_branches.append(index)
#                 if mul is not None and is_multiply_valid(mul, scope):
#                     valid_branches.append(mul)
#                 if len(valid_branches) == 0:
#                     raise ValueError(f'ERROR: no valid branches for QJux. must have at exactly one. {ast=}')
#                 if len(valid_branches) > 1:
#                     raise ValueError(f'ERROR: multiple valid branches for QJux. must have exactly one. {ast=}')

#                 # overwrite QJux with the valid branch
#                 valid_branch, = valid_branches
#                 # typecheck_and_resolve(valid_branch, scope) #manually typechecking here since current __full_traversal_iter doesn't recurse into newly sent children... consider adjusting
#                 gen.send(valid_branch)

#                 # pdb.set_trace()
#                 # ...
#                 # return valid_branches[0], scope
#             case Call(f=f, args=args):
#                 # TODO: check if the signature of f agrees with the args...
#                 # print(f'skipping function typechecking...')
#                 ...

#             case Int(): ...

#             case _:
#                 pdb.set_trace()
#                 ...
#                 raise ValueError(f'INTERNAL ERROR: typecheck_and_resolve not implemented for {type(ast)}')



#     pdb.set_trace()
#     return ast.items[0], scope
#     ...
# #     """Check if the given AST is well-formed from a type perspective"""
# #     match ast:
# #         case Call(): return typecheck_call(ast, scope)
# #         case Index(): return typecheck_index(ast, scope)
# #         case Mul(): return typecheck_binary_dispatch(ast, scope)
# #         case _: raise NotImplementedError(f'typecheck not implemented for {type(ast)}')

# # def infer_types(ast: AST, scope: Scope) -> AST:

def strip_group(ast: AST) -> AST:
    while isinstance(ast, Group):
        assert len(ast.items) == 1, f'expected single item in Group, got {ast.items}'
        ast = ast.items[0]
    return ast

def is_call_valid(ast: Call, scope: Scope) -> bool:
    f_type = typeof(ast.f, scope)
    # if isinstance(f_type, ReturnTyped):
    #     # TODO: check if args match the function signature.
    #     #       for now, just skip
    #     return True
    
    if isinstance(f_type, ReturnTyped):
        return True
    
    if not hasattr(f_type, 't'):
        pdb.set_trace()
        raise ValueError(f'INTERNAL ERROR: typeof returned non-Type: {f_type}')
    
    if issubclass(f_type.t, (FunctionLiteral, CallableBase)):
        # TODO: check if args match the function signature.
        #       for now, just skip
        return True
    return False


def is_index_valid(ast: Index, scope: Scope) -> bool:
    pdb.set_trace()
    ...

def is_multiply_valid(ast: Mul, scope: Scope) -> bool:
    # early short circuit for common case
    left_type = typeof(ast.left, scope)
    if isinstance(left_type, ReturnTyped):
        return False
    if issubclass(left_type.t, (FunctionLiteral, CallableBase)):
        return False

    # TBD this is technically true, but it implies you can call functions on the right side when you can't
    # instead at this point it probably should just be a general case...
    right_type = typeof(ast.right, scope)
    if issubclass(right_type.t, (FunctionLiteral, CallableBase)):
        return False


    # TODO: probably need some sort of proper table for keeping track of multipliable types
    pdb.set_trace()
    ...



def typeof_identifier(ast: Identifier, scope: Scope, params:bool=False) -> TypeExpr:
    var = scope.get(ast.name)
    if var is None:
        raise KeyError(f'variable "{ast.name}" not found in scope')
    if var.type is not untyped:
        return var.type

    return typeof(var.value, scope, params)



# abstract base type to register new callable types
class CallableBase(AST): ...
#TODO: this is used by the interpreter. remove when compiler type checking is complete and can replace interpreter stuff
_callable_types = (PrototypeBuiltin, FunctionLiteral, CallableBase, ReturnTyped)
# def register_callable(cls: type[AST]):
#     _callable_types.append(cls)

def typeof_call(ast: Call, scope: Scope, params:bool=False) -> TypeExpr:
    f_type = type(ast.f)
    if f_type in _external_typeof_call_fn_map:
        return _external_typeof_call_fn_map[f_type](ast.f, ast.args, scope, params)

    if not isinstance(ast.f, Identifier):
        raise NotImplementedError(f"calling non-identifier functions is not implemented yet. {ast.f} called with args {ast.args}")
        # get the return type of the function

    f_var = scope.get(ast.f.name)
    # TODO: need to be able to register e.g. a dict[type[AST], Callable[[AST], Type]]
    # if is_index_valid(f_var.value, Builtin) # b.c. Builtin is only defined in the backend, not here...

    pdb.set_trace()
    # match f_var.value:
    #     case FunctionLiteral(return_type=dewy_return_type):# | Builtin(return_type=dewy_return_type) | Closure(FunctionLiteral(return_type=dewy_return_type)):
    #         # dewy_return_type = return_type
    #         if not isinstance(dewy_return_type, Type):
    #             dewy_return_type = typeof(dewy_return_type, scope)
    #         ret_type = dewy_qbe_type_map[dewy_return_type]
    #     case _:
    #         raise ValueError(f'Unrecognized AST type to call: {f_var.value!r}')


# def simple_typecheck_resolve_ast(ast: AST, scope: Scope) -> AST:
#     """Resolve the AST to a type. This is a simple version that doesn't do any complex type checking"""
#     if isinstance(ast, Identifier):
#         var = scope.get(ast.name)
#         return var.value
#     if isinstance(ast, AtHandle):
#         return ast.operand
#     if isinstance(ast, Group):
#         pdb.set_trace()
#         ...
#     if isinstance(ast, Access):
#         pdb.set_trace()
#         ...

#     # no resolving possible
#     return ast

def typecheck_call(ast: Call, scope: Scope) -> bool:
    #For now, just the simplest check. is f callable. ignore rest of type checking
    f_type = typeof(ast.f, scope)
    if not isinstance(f_type, Type):
        pdb.set_trace()
        ...
        #TBD how to handle the different TypeExpr's

    if isinstance(f_type, Type) and issubclass(f_type.t, _callable_types):
        return True

    return False
    pdb.set_trace()
    # f = ast.f
    # f = simple_typecheck_resolve_ast(f, scope) # resolve to a value
    # if isinstance(f, Identifier):
    #     var = scope.get(f.name)
    #     f = var.value
    # if isinstance(f, AtHandle):
    #     f = f.operand

    if isinstance(f, tuple(_callable_types)):
        #TODO: longer term, want to check that the expected args match the given args
        return True

    # if isinstance(f, Group):
    #     pdb.set_trace()
    #     # get the type of the group items... handling void, and if multiple, then answer is False...
    #     ...
    # if isinstance(f, Access):
    #     pdb.set_trace()
    #     ...
    #TODO: replace all this with full typechecking...
    # t = typeof(f, scope)
    # if t in _callable_types: return True
    # return False
    return False


# Abstract base types to register new indexable/indexer types
class IndexableBase(AST): ...
class IndexerBase(AST): ...

_indexable_types = (Array, Range, IndexableBase)
_indexer_types = (Array, Range, IndexerBase)
# def register_indexable(cls: type[AST]):
#     _indexable_types.append(cls)
# def register_indexer(cls: type[AST]):
#     _indexer_types.append(cls)

def typeof_index(ast: Index, scope: Scope, params:bool=False) -> TypeExpr:
    pdb.set_trace()
    ...

def typecheck_index(ast: Index, scope: Scope) -> bool:
    # left = simple_typecheck_resolve_ast(ast.left, scope)
    # right = simple_typecheck_resolve_ast(ast.right, scope)
    # if isinstance(left, _indexable_types) and isinstance(right, _indexer_types):
    #     return True


    #for now super simple checks on left and right
    left_type = typeof(ast.left, scope)
    right_type = typeof(ast.right, scope)
    if not isinstance(left_type, Type) or not isinstance(right_type, Type):
        pdb.set_trace()
        #TODO: more complex cases involving type expressions...
        raise NotImplementedError('typecheck_index not implemented for non-Type left side')

    if issubclass(left_type.t, _indexable_types) and issubclass(right_type.t, _indexer_types):
        return True

    return False



# abstract base type to register new multipliable types
class MultipliableBase(AST): ...
_multipliable_types = (Int, Array, Range, MultipliableBase) #TODO: add more types
# def register_multipliable(cls: type[AST]):
#     _multipliable_types.append(cls)
def typecheck_multiply(ast: Mul, scope: Scope) -> bool:
    # left = simple_typecheck_resolve_ast(ast.left, scope)
    # right = simple_typecheck_resolve_ast(ast.right, scope)
    # if isinstance(left, _multipliable_types) and isinstance(right, _multipliable_types):
    #     return True

    #TODO: full type checking to check if values are multipliable
    # pdb.set_trace()
    left_type = typeof(ast.left, scope)
    right_type = typeof(ast.right, scope)
    if not isinstance(left_type, Type) or not isinstance(right_type, Type):
        pdb.set_trace()
        raise NotImplementedError('typecheck_multiply not implemented for non-Type left side')

    if issubclass(left_type.t, _multipliable_types) and issubclass(right_type.t, _multipliable_types):
        return True

    return False



def typeof_group(ast: Group, scope: Scope, params:bool=False) -> TypeExpr:
    expressed: list[TypeExpr] = []
    for expr in ast.items:
        res = typeof(expr, scope, params)
        if res is not void:
            expressed.append(res)
    if len(expressed) == 0:
        return Type(Void)
    if len(expressed) == 1:
        return expressed[0]
    return Type(Group, parameters=TypeParam(expressed))


def typeof_block(ast: Block, scope: Scope, params:bool=False) -> TypeExpr:
    scope = Scope(scope)
    return typeof_group(Group(ast.items), scope, params)






def typeof_at_handle(ast: AtHandle, scope: Scope, params:bool=False) -> TypeExpr:
    if not isinstance(ast.operand, Identifier):
        raise NotImplementedError('typeof_at_handle only implemented for Identifiers')
    return typeof_identifier(ast.operand, scope, params)


def typeof_express(ast: Express, scope: Scope, params:bool=False) -> TypeExpr:
    var = scope.get(ast.id.name)

    # if we were told what the type is, return that (as it should be the main source of truth)
    # TODO: perhaps we return this if it's not untyped/void/etc.
    if isinstance(var.type, (Type, ReturnTyped)) and var.type is not untyped:
        return var.type

    return typeof(var.value, scope, params)

logical_binop_typemap = {
    (Int, Int): Int,
    (Bool, Bool): Bool,
}
def typeof_logical_binop(ast: And|Or|Xor|Nand|Nor|Xnor, scope: Scope, params:bool=False) -> TypeExpr:
    """and or xor nand nor xnor"""
    left_type = typeof(ast.left, scope)
    right_type = typeof(ast.right, scope)

    if not isinstance(left_type, Type) or not isinstance(right_type, Type):
        raise NotImplementedError('typeof_logical_binop not implemented for non-Type left side')

    key = (left_type.t, right_type.t)
    if not key in logical_binop_typemap:
        raise NotImplementedError(f'logical_binop_typemap not implemented for {key}. {ast=}')

    return Type(logical_binop_typemap[key])

def typeof_binary_dispatch(ast: BinOp, scope: Scope, params:bool=False) -> TypeExpr:
    # just do the easy cases for now
    if isinstance(ast, (Add, Sub, Mul, Mod, IDiv, Pow, LeftShift, RightShift)):
        left_type = typeof(ast.left, scope)
        right_type = typeof(ast.right, scope)
        if not isinstance(left_type, Type) or not isinstance(right_type, Type):
            raise NotImplementedError(f'typeof_binary_dispatch not implemented for non-Type left/right side. {left_type=}, {right_type=}')

        # deal with possibly untyped values
        if left_type is untyped and right_type is untyped:
            raise ValueError(f'ERROR: typeof_binary_dispatch requires at least one side to not be `untyped`. Got {left_type=}, {right_type=}. {ast=}')
        if left_type is untyped:
            left_type = right_type
        if right_type is untyped:
            right_type = left_type

        if left_type.t != right_type.t:
            raise ValueError(f'INTERNAL ERROR: typeof_binary_dispatch called with mismatched types. {left_type=}, {right_type=}')

        return left_type

    pdb.set_trace()
    raise NotImplementedError('typeof_binary_dispatch not implemented')

def typecheck_binary_dispatch(ast: BinOp, scope: Scope) -> bool:
    op = type(ast)
    if op not in binary_dispatch_table:
        return False
    left_type = typeof(ast.left, scope)
    right_type = typeof(ast.right, scope)
    if not isinstance(left_type, Type) or not isinstance(right_type, Type):
        pdb.set_trace()
        raise NotImplementedError('typecheck_binary_dispatch not implemented for non-Type left side')

    if (left_type.t, right_type.t) not in binary_dispatch_table[op]:
        return False

    return True

def typeof_array(ast: Array, scope: Scope, params:bool=False) -> TypeExpr:
    if not params:
        return Type(Array)
    pdb.set_trace()
    ...
    raise NotImplementedError('typeof_array not implemented when params=True')






class ObjectBase(AST): ...

def typeof_access(ast: Access, scope: Scope, params:bool=False) -> TypeExpr:
    left = typeof(ast.left, scope, params)

    # happy path: left was an object
    if isinstance(left, Type) and issubclass(left.t, ObjectBase) and left.parameters is not None:
        parameters = left.parameters
        assert len(parameters.items) == 1, f'expected only one parameter for object access. {parameters=}'
        scope, = parameters.items
        assert isinstance(scope, Scope), f'expected parameter to be a scope. {parameters.items[0]=}'
        if isinstance(ast.right, Identifier):
            handle, id = False, ast.right
        elif isinstance(ast.right, AtHandle):
            handle, id = True, ast.right.operand
            assert isinstance(id, Identifier), f'expected id to be an Identifier. {id=}. Other types not yet supported'
        elif isinstance(ast.right, Access):
            raise ValueError('Right hand side should not be access. Access should be left associative')
        else:
            raise NotImplementedError(f'Access right-hand-side not implemented for {type(ast.right)}')

        if handle:
            return typeof_identifier(id, scope, params)
        return typeof_express(Express(id), scope, params)



    pdb.set_trace()
    raise NotImplementedError(f'typeof_access not implemented for {type(ast)}')



def typeof_iter_in(ast: IterIn, scope: Scope, params:bool=False) -> TypeExpr:
    right = typeof(ast.right, scope, params)
    pdb.set_trace()
    ...



# TODO: for now, just a super simple dispatch table
binary_dispatch_table = {
    Mul: {
        (Int, Int): Int,
        # (Int, Float): Float,
        # (Float, Float): Float,
    }
}




# UnaryDispatchKey =  tuple[type[UnaryPrefixOp]|type[UnaryPostfixOp], type[SimpleValue[T]]]
# unary_dispatch_table: dict[UnaryDispatchKey[T], TypingCallable[[T], AST]] = {
#     (Not, Int): lambda l: Int(~l),
#     (Not, Bool): lambda l: Bool(not l),
#     (UnaryPos, Int): lambda l: Int(l),
#     (UnaryNeg, Int): lambda l: Int(-l),
#     (UnaryMul, Int): lambda l: Int(l),
#     (UnaryDiv, Int): lambda l: Int(1/l),
# }

# BinaryDispatchKey = tuple[type[BinOp], type[SimpleValue[T]], type[SimpleValue[U]]]
# # These are all symmetric meaning you can swap the operand types and the same function will be used (but the arguments should not be swapped)
# binary_dispatch_table: dict[BinaryDispatchKey[T, U], TypingCallable[[T, U], AST]|TypingCallable[[U, T], AST]] = {
#     (And, Int, Int): lambda l, r: Int(l & r),
#     (And, Bool, Bool): lambda l, r: Bool(l and r),
#     (Or, Int, Int): lambda l, r: Int(l | r),
#     (Or, Bool, Bool): lambda l, r: Bool(l or r),
#     (Xor, Int, Int): lambda l, r: Int(l ^ r),
#     (Xor, Bool, Bool): lambda l, r: Bool(l != r),
#     (Nand, Int, Int): lambda l, r: Int(~(l & r)),
#     (Nand, Bool, Bool): lambda l, r: Bool(not (l and r)),
#     (Nor, Int, Int): lambda l, r: Int(~(l | r)),
#     (Nor, Bool, Bool): lambda l, r: Bool(not (l or r)),
#     (Add, Int, Int): lambda l, r: Int(l + r),
#     (Add, Int, Float): lambda l, r: Float(l + r),
#     (Add, Float, Float): lambda l, r: Float(l + r),
#     (Sub, Int, Int): lambda l, r: Int(l - r),
#     (Sub, Int, Float): lambda l, r: Float(l - r),
#     (Sub, Float, Float): lambda l, r: Float(l - r),
#     (Mul, Int, Int): lambda l, r: Int(l * r),
#     (Mul, Int, Float): lambda l, r: Float(l * r),
#     (Mul, Float, Float): lambda l, r: Float(l * r),
#     (Div, Int, Int): int_int_div,
#     (Div, Int, Float): float_float_div,
#     (Div, Float, Float): float_float_div,
#     (Mod, Int, Int): lambda l, r: Int(l % r),
#     (Mod, Int, Float): lambda l, r: Float(l % r),
#     (Mod, Float, Float): lambda l, r: Float(l % r),
#     (Pow, Int, Int): lambda l, r: Int(l ** r),
#     (Pow, Int, Float): lambda l, r: Float(l ** r),
#     (Pow, Float, Float): lambda l, r: Float(l ** r),
#     (Less, Int, Int): lambda l, r: Bool(l < r),
#     (Less, Int, Float): lambda l, r: Bool(l < r),
#     (Less, Float, Float): lambda l, r: Bool(l < r),
#     (LessEqual, Int, Int): lambda l, r: Bool(l <= r),
#     (LessEqual, Int, Float): lambda l, r: Bool(l <= r),
#     (LessEqual, Float, Float): lambda l, r: Bool(l <= r),
#     (Greater, Int, Int): lambda l, r: Bool(l > r),
#     (Greater, Int, Float): lambda l, r: Bool(l > r),
#     (Greater, Float, Float): lambda l, r: Bool(l > r),
#     (GreaterEqual, Int, Int): lambda l, r: Bool(l >= r),
#     (GreaterEqual, Int, Float): lambda l, r: Bool(l >= r),
#     (GreaterEqual, Float, Float): lambda l, r: Bool(l >= r),
#     (Equal, Int, Int): lambda l, r: Bool(l == r),
#     (Equal, Float, Float): lambda l, r: Bool(l == r),
#     (Equal, Bool, Bool): lambda l, r: Bool(l == r),
#     (Equal, String, String): lambda l, r: Bool(l == r),
#     # (NotEqual, Int, Int): lambda l, r: Bool(l != r),

# }

# unsymmetric_binary_dispatch_table: dict[BinaryDispatchKey[T, U], ] = {
#     #e.g. (Mul, String, Int): lambda l, r: String(l * r), # if we follow python's behavior
# }

# # dispatch table for more complicated values that can't be automatically unpacked by the dispatch table
# # TODO: actually ideally just have a single table
# CustomBinaryDispatchKey = tuple[type[BinOp], type[T], type[U]]
# custom_binary_dispatch_table: dict[CustomBinaryDispatchKey[T, U], TypingCallable[[T, U], AST]] = {
#     (Add, Array, Array): lambda l, r: Array(l.items + r.items), #TODO: this will be removed in favor of spread. array add will probably be vector add
#     # (BroadcastOp, Array, Array): broadcast_array_op,
#     # (BroadcastOp, NpArray, NpArray): broadcast_array_op,
#     # (BroadcastOp, Int, Array): broadcast_array_op,
#     # (BroadcastOp, Float, Array): broadcast_array_op,

# }
