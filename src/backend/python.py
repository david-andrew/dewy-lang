from dataclasses import dataclass

from src.postparse import post_parse

from ..tokenizer import tokenize
from ..postok import post_process
from ..parser import top_level_parse, Scope
from ..syntax import (
    AST,
    Type,
    ListOfASTs, Tuple, Block, Array, Group, Range, Object, Dict,
    TypedIdentifier,
    Void, void, Undefined, undefined,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    PrototypeIdentifier, Identifier, Express,
    FunctionLiteral, PrototypePyAction, PyAction, Call,
    Assign,
    Int, Bool,
    Range, IterIn,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv,
    # DeclarationType,
)
from pathlib import Path
from typing import Protocol, cast
from functools import cache

import pdb



def python_interpreter(path: Path, args: list[str]):

    with open(path) as f:
        src = f.read()

    tokens = tokenize(src)
    post_process(tokens)

    ast = top_level_parse(tokens)
    ast = post_parse(ast)

    #TODO: put these under a verbose/etc. flag
    print_ast(ast)
    print(repr(ast))

    res = top_level_evaluate(ast)
    if res is not void:
        print(res)

def print_ast(ast: AST):
    """little helper function to print out the equivalent source code of an AST"""
    print('```dewy')
    if isinstance(ast, (Block, Group)):
        for i in ast: print(i)
    else:
        print(ast)
    print('```')


def top_level_evaluate(ast:AST) -> AST:
    scope = Scope.default()
    insert_pyactions(scope)
    return evaluate(ast, scope)


class EvalFunc[T](Protocol):
    def __call__(self, ast: T, scope: Scope) -> AST: ...


def no_op[T](ast: T, scope: Scope) -> T:
    """For ASTs that just return themselves when evaluated"""
    return ast

def cannot_evaluate(ast: AST, scope: Scope) -> AST:
    raise ValueError(f'INTERNAL ERROR: evaluation of type {type(ast)} is not possible')


@cache
def get_eval_fn_map() -> dict[type[AST], EvalFunc]:
    return {
        Call: evaluate_call,
        Block: evaluate_block,
        Group: evaluate_group,
        Assign: evaluate_assign,
        FunctionLiteral: evaluate_function_literal,
        Closure: evaluate_closure,
        PyAction: evaluate_pyaction,
        String: no_op,
        IString: evaluate_istring,
        Identifier: cannot_evaluate,
        Express: evaluate_express,
        #TODO: other AST types here
    }

def evaluate(ast:AST, scope:Scope) -> AST:
    eval_fn_map = get_eval_fn_map()

    ast_type = type(ast)
    if ast_type in eval_fn_map:
        return eval_fn_map[ast_type](ast, scope)

    raise NotImplementedError(f'evaluation not implemented for {ast_type}')



def evaluate_call(ast: Call, scope: Scope) -> AST:
    f = ast.f
    if isinstance(f, Identifier):
        f = scope.get(f.name).value
    assert isinstance(f, (PyAction, Closure)), f'expected Function or PyAction, got {f}'

    if isinstance(f, PyAction):
        args, kwargs = collect_args(ast.args, scope)
        return f.action(*args, **kwargs, scope=scope)

    if isinstance(f, Closure):
        args, kwargs = collect_args(ast.args, scope)
        return evaluate(f.fn.body, f.scope)

    pdb.set_trace()
    raise NotImplementedError(f'Function evaluation not implemented yet')

def collect_args(args: AST | None, scope: Scope) -> tuple[list[AST], dict[str, AST]]:
    match args:
        case None: return [], {}
        case Identifier(name): return [scope.get(name).value], {}
        case Assign(): raise NotImplementedError('Assign not implemented yet')
        # case Tuple(items): raise NotImplementedError('Tuple not implemented yet')
        case String() | IString(): return [args], {}
        case _: raise NotImplementedError(f'collect_args not implemented yet for {args}')


    raise NotImplementedError(f'collect_args not implemented yet for {args}')

def evaluate_group(ast: Group, scope: Scope):

    expressed: list[AST] = []
    for expr in ast.items:
        res = evaluate(expr, scope)
        if res is not void:
            expressed.append(res)
    if len(expressed) == 0:
        return void
    if len(expressed) == 1:
        return expressed[0]
    raise NotImplementedError(f'Block with multiple expressions not yet supported. {ast=}, {expressed=}')


def evaluate_block(ast: Block, scope: Scope):
    scope = Scope(scope)
    return evaluate_group(Group(ast.items), scope)


def evaluate_assign(ast: Assign, scope: Scope):
    match ast:
        case Assign(left=Identifier(name), right=right):
            right = evaluate(right, scope)
            scope.assign(name, right)
            return void
    pdb.set_trace()
    raise NotImplementedError('Assign not implemented yet')

class Closure(AST):
    fn: FunctionLiteral
    scope: Scope
    # call_args: AST|None=None # TBD how to handle
    def __str__(self):
        return f'Closure({self.fn}, scope={self.scope})'

def evaluate_function_literal(ast: FunctionLiteral, scope: Scope):
    return Closure(fn=ast, scope=scope)

def evaluate_closure(ast: Closure, scope: Scope):
    fn_scope = Scope(ast.scope)
    #TODO: for now we assume everything is 0 args. need to handle args being attached to the closure
    return evaluate(ast.fn.body, fn_scope)

    #grab arguments from scope and put them in fn_scope
    pdb.set_trace()
    ast.fn.args
    raise NotImplementedError('Closure not implemented yet')

def evaluate_pyaction(ast: PyAction, scope: Scope):
    # fn_scope = Scope(ast.scope)
    #TODO: currently just assuming 0 args in and no return
    return ast.action(scope)


def evaluate_istring(ast: IString, scope: Scope) -> String:
    parts = (py_stringify(i, scope) for i in ast.parts)
    return String(''.join(parts))


def evaluate_express(ast: Express, scope: Scope):
    val = scope.get(ast.id.name).value
    return evaluate(val, scope)


######################### Builtin functions and helpers ############################
def py_stringify(ast: AST, scope: Scope) -> str:
    ast = evaluate(ast, scope)
    match ast:
        case String(val): return val
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'stringify not implemented for {type(ast)}')
    pdb.set_trace()

    raise NotImplementedError('stringify not implemented yet')

def py_printl(s:String|IString, scope: Scope) -> Void:
    py_print(s, scope)
    print()
    return void

def py_print(s:String|IString, scope: Scope) -> Void:
    if not isinstance(s, (String, IString)):
        raise ValueError(f'py_print expected String or IString, got {type(s)}:\n{s!r}')
    if isinstance(s, IString):
        s = cast(String, evaluate(s, scope))
    print(s.val, end='')
    return void

def py_readl(scope: Scope) -> String:
    return String(input())

def insert_pyactions(scope: Scope):
    """replace pyaction stubs with actual implementations"""
    if 'printl' in scope.vars:
        assert isinstance((proto:=scope.vars['printl'].value), PrototypePyAction)
        scope.vars['printl'].value = PyAction(proto.args, py_printl, proto.return_type)
    if 'print' in scope.vars:
        assert isinstance((proto:=scope.vars['print'].value), PrototypePyAction)
        scope.vars['print'].value = PyAction(proto.args, py_print, proto.return_type)
    if 'readl' in scope.vars:
        assert isinstance((proto:=scope.vars['readl'].value), PrototypePyAction)
        scope.vars['readl'].value = PyAction(proto.args, py_readl, proto.return_type)
