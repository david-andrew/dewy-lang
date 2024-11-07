from ...tokenizer import tokenize
from ...postok import post_process
from ...dtypes import (
    Scope as DTypesScope,
    typecheck_call, typecheck_index, typecheck_multiply,
    register_typeof, short_circuit,
    CallableBase, IndexableBase, IndexerBase, MultipliableBase, ObjectBase,
)
from ...parser import top_level_parse, QJux
from ...syntax import (
    AST,
    Type, TypeParam,
    PointsTo, BidirPointsTo,
    ListOfASTs, PrototypeTuple, Block, Array, Group, Range, ObjectLiteral, Dict, BidirDict, UnpackTarget,
    TypedIdentifier,
    Void, void, Undefined, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    Identifier, Express, Declare,
    PrototypePyAction, Call, Access, Index,
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
)

from ...postparse import post_parse, FunctionLiteral, Signature, normalize_function_args
from ...utils import Options

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast, Callable as TypingCallable, Any, Generic, Literal
from functools import cache
from collections import defaultdict
from types import SimpleNamespace
from itertools import count


import pdb


from functools import cache
from pathlib import Path
from ...utils import Options


# TODO: not quite sure what to do about scope. for now, just steal from
from ..python import Scope, Closure

# command to compile a .qbe file to an executable
# qbe <file>.ssa | gcc -x assembler -static -o hello 

def qbe_compiler(path: Path, args: list[str], options: Options) -> None:
    # get the source code and tokenize
    src = path.read_text()
    tokens = tokenize(src)
    post_process(tokens)

    # parse tokens into AST
    ast = top_level_parse(tokens)
    ast = post_parse(ast)

    # debug printing
    if options.verbose:
        print(repr(ast))

    # run the program
    ssa = top_level_compile(ast)
    print(ssa)



def top_level_compile(ast: AST) -> str:
    scope = Scope.default()
    return compile(ast, scope)



global_counter = count(0)


# TODO: include user defined struct types...
QbeType = Literal['w', 'l', 's', 'd', 'b', 'h']

@dataclass
class QbeBlock:
    label: str
    lines: list[str]

    def __str__(self) -> str:
        return '\n    '.join([self.label, *self.lines])

@dataclass
class QbeArg:
    name: str
    type: QbeType

    def __str__(self) -> str:
        return f'{self.type} {self.name}'

@dataclass
class QbeFunction:
    name: str
    export: bool
    args: list[QbeArg]
    ret: QbeType
    blocks: list[QbeBlock]

    def __str__(self) -> str:
        export = 'export ' if self.export else ''
        args = ', '.join(map(str, self.args))
        ret = f'{self.ret} ' if self.ret else ''
        blocks = '\n'.join(map(str, self.blocks))
        return f'{export}function {ret}{self.name}({args}) {{\n{blocks}\n}}'

@dataclass
class QbeModule:
    functions: list[QbeFunction] = field(default_factory=list)
    global_data: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        functions = '\n\n'.join(map(str, self.functions))
        global_data = '\n'.join(self.global_data)
        return f'{global_data}\n\n{functions}'


from typing import Protocol, TypeVar
T = TypeVar('T', bound=AST)
U = TypeVar('U', bound=AST)
class CompileFunc(Protocol):
    def __call__(self, ast: T, scope: Scope) -> str: ...



@cache
def get_compile_fn_map() -> dict[type[AST], CompileFunc]:
    return {
        # Declare: compile_declare,
        QJux: compile_qjux,
        Call: compile_call,
        # Block: compile_block,
        # Group: compile_group,
        # Array: compile_array,
        # Dict: compile_dict,
        # PointsTo: compile_points_to,
        # BidirDict: compile_bidir_dict,
        # BidirPointsTo: compile_bidir_points_to,
        # ObjectLiteral: compile_object_literal,
        # Object: no_op,
        # Access: compile_access,
        # Index: compile_index,
        # Assign: compile_assign,
        # IterIn: compile_iter_in,
        # FunctionLiteral: compile_function_literal,
        # Closure: compile_closure,
        # PyAction: compile_pyaction,
        String: compile_string,
        # IString: compile_istring,
        # Identifier: cannot_evaluate,
        # Express: compile_express,
        # Int: no_op,
        # Float: no_op,
        # Bool: no_op,
        # Range: no_op,
        # Flow: compile_flow,
        # Default: compile_default,
        # If: compile_if,
        # Loop: compile_loop,
        # UnaryPos: compile_unary_dispatch,
        # UnaryNeg: compile_unary_dispatch,
        # UnaryMul: compile_unary_dispatch,
        # UnaryDiv: compile_unary_dispatch,
        # Not: compile_unary_dispatch,
        # Greater: compile_binary_dispatch,
        # GreaterEqual: compile_binary_dispatch,
        # Less: compile_binary_dispatch,
        # LessEqual: compile_binary_dispatch,
        # Equal: compile_binary_dispatch,
        # And: compile_binary_dispatch,
        # Or: compile_binary_dispatch,
        # Xor: compile_binary_dispatch,
        # Nand: compile_binary_dispatch,
        # Nor: compile_binary_dispatch,
        # Xnor: compile_binary_dispatch,
        # Add: compile_binary_dispatch,
        # Sub: compile_binary_dispatch,
        # Mul: compile_binary_dispatch,
        # Div: compile_binary_dispatch,
        # Mod: compile_binary_dispatch,
        # Pow: compile_binary_dispatch,
        # AtHandle: compile_at_handle,
        # Undefined: no_op,
        # Void: no_op,
        # #TODO: other AST types here
    }



def compile(ast:AST, scope:Scope) -> str:
    compile_fn_map = get_compile_fn_map()

    ast_type = type(ast)
    if ast_type in compile_fn_map:
        return compile_fn_map[ast_type](ast, scope)

    raise NotImplementedError(f'AST type {ast_type} not implemented yet')

def compile_qjux(ast: QJux, scope: Scope) -> AST:
    if ast.call is not None and typecheck_call(ast.call, scope):
        return compile_call(ast.call, scope)
    if ast.index is not None and typecheck_index(ast.index, scope):
        return compile_index(ast.index, scope)
    if typecheck_multiply(ast.mul, scope):
        return compile_binary_dispatch(ast.mul, scope)

    raise ValueError(f'Typechecking failed to match a valid evaluation for QJux. {ast=}')



def compile_string(ast: String, scope: Scope) -> str:
    pdb.set_trace()
    ...

def compile_call(call: Call, scope: Scope) -> str:
    f = call.f

    # get the expression of the group
    if isinstance(f, Group):
        pdb.set_trace()
        f = evaluate(f, scope)

    # get the value pointed to by the identifier
    if isinstance(f, Identifier):
        f = scope.get(f.name).value

    # if this is a handle, do a partial evaluation rather than a call
    if isinstance(f, AtHandle):
        pdb.set_trace()
        return apply_partial_eval(f.operand, call.args, scope)

    # AST being called must be TypingCallable
    assert isinstance(f, (PrototypePyAction, Closure)), f'expected Function or PyAction, got {f}'

    # save the args of the call as metadata for the function AST
    call_args, call_kwargs = collect_calling_args(call.args, scope)
    scope.meta[f].call_args = call_args, call_kwargs

    # run the function and return the result
    if isinstance(f, PrototypePyAction):
        return compile_call_pyaction(f, scope)
    if isinstance(f, Closure):
        return compile_call_closure(f, scope)

    pdb.set_trace()
    raise NotImplementedError(f'Function evaluation not implemented yet')





#TODO: longer term this might also return a list/dict of spread args passed into the function
def collect_calling_args(args: AST | None, scope: Scope) -> tuple[list[AST], dict[str, AST]]:
    """
    Collect the arguments that a function is being called with
    e.g. `let fn = (a b c) => a + b + c; fn(1 c=2 3)`
    then the calling args are [1, 3] and {c: 2}

    Args:
        args: the arguments being passed to the function. If None, then treat as a no-arg call
        scope: the scope in which the function is being called

    Returns:
        a tuple of the positional arguments and keyword arguments
    """
    match args:
        case None | Void(): return [], {}
        case Identifier(name): return [scope.get(name).value], {}
        case Assign(left=Identifier(name)|TypedIdentifier(id=Identifier(name)), right=right): return [], {name: right}
        # case Assign(left=UnpackTarget() as target, right=right): raise NotImplementedError('UnpackTarget not implemented yet')
        case Assign(): raise NotImplementedError('Assign not implemented yet') #called recursively if a calling arg was an keyword arg rather than positional
        case CollectInto(right=right):
            pdb.set_trace()
            ... #right should be iterable, so extend with the values it expresses
                #whether to add to args or kwargs depends on each type from right
            val = evaluate(right, scope)
            match val:
                case Array(items): ... #return [collect_calling_args(i, scope) for i in items]
        case Group(items):
            call_args, call_kwargs = [], {}
            for i in items:
                a, kw = collect_calling_args(i, scope)
                call_args.extend(a)
                call_kwargs.update(kw)
            return call_args, call_kwargs

        #TODO: eventually it should just be anything that is left over is positional args rather than specifying them all out
        case Int() | String() | IString() | Range() | Call() | Access() | Index() | Express() | QJux() | UnaryPrefixOp() | UnaryPostfixOp() | BinOp() | BroadcastOp():
            return [args], {}
        # case Call(): return [args], {}
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'collect_args not implemented yet for {args}')


    raise NotImplementedError(f'collect_args not implemented yet for {args}')










def compile_call_pyaction(f: PrototypePyAction, scope: Scope) -> str:
    pdb.set_trace()
    ...


def compile_call_closure(f: Closure, scope: Scope) -> str:
    pdb.set_trace()
    ...