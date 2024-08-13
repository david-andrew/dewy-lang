from dataclasses import dataclass

from ..tokenizer import tokenize
from ..postok import post_process
from ..parser import top_level_parse, Scope
from ..syntax import (
    AST,
    Type,
    ListOfASTs, Tuple, Block, Array, Group, Range, Object, Dict,
    TypedIdentifier,
    void, undefined,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    Identifier,
    Function, PyAction, Call,
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
from typing import Protocol
from functools import cache

import pdb

def python_interpreter(path: Path, args: list[str]):

    with open(path) as f:
        src = f.read()

    tokens = tokenize(src)
    post_process(tokens)

    ast = top_level_parse(tokens)
    # print(f'parsed AST: {ast}\n{repr(ast)}')
    from ..syntax import Block
    print('```dewy')
    if isinstance(ast, (Block, Group)):
        for i in ast: print(i)
    else:
        print(ast)
    print('```')
    print(repr(ast))
    return #DEBUG while not done evaluate implementation
    # raise NotImplementedError("evaluation hasn't been implemented yet")

    res = top_level_evaluate(ast)
    if res and res is not void:
        print(res)



def top_level_evaluate(ast:AST) -> AST|None:
    scope = Scope.default()
    return evaluate(ast, scope)


class EvalFunc[T](Protocol):
    def __call__(self, ast: T, scope: Scope) -> AST: ...

@cache
def get_eval_fn_map() -> dict[type[AST], EvalFunc]:
    return {
        Call: evaluate_call,
        Block: evaluate_block,
        #TODO: other AST types here
    }

def evaluate(ast:AST, scope:Scope) -> AST|None:
    eval_fn_map = get_eval_fn_map()

    ast_type = type(ast)
    if ast_type in eval_fn_map:
        return eval_fn_map[ast_type](ast, scope)

    raise NotImplementedError(f'evaluation not implemented for {ast_type}')



def evaluate_call(ast: Call, scope: Scope) -> AST: #(f: AST, f_args: AST | None, scope: Scope) -> AST:
    f = ast.f
    if isinstance(f, Identifier):
        f = scope.get(f.name).value
    assert isinstance(f, (Function, PyAction)), f'expected Function or PyAction, got {f}'

    if isinstance(f, PyAction):
        args, kwargs = collect_args(ast.args, scope)
        return f.action(*args, **kwargs)

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

def evaluate_block(ast: Block, scope: Scope):
    pdb.set_trace()
    return void
    raise NotImplementedError('Block evaluation not implemented yet')
