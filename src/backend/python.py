from dataclasses import dataclass

from ..tokenizer import tokenize
from ..postok import post_process
from ..parser import top_level_parse, Scope
from ..syntax import (
    AST,
    void,
    Function, PyAction, Call,
    Identifier,
    Assign,
    Tuple,
    Array,
    String, IString,

)
from pathlib import Path

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
    if isinstance(ast, Block):
        for i in ast: print(i)
    else:
        print(ast)
    print('```')
    print(repr(ast))
    # return
    # raise NotImplementedError("evaluation hasn't been implemented yet")

    res = top_level_evaluate(ast)
    if res and res is not void:
        print(res)



def top_level_evaluate(ast:AST) -> AST|None:
    scope = Scope.default()
    return evaluate(ast, scope)

def evaluate(ast:AST, scope:Scope) -> AST|None:

    match ast:
        case Call(f, args): return evaluate_call(f, args, scope)

    pdb.set_trace()


def evaluate_call(f: AST, f_args: AST | None, scope: Scope) -> AST:
    if isinstance(f, Identifier):
        f = scope.get(f.name).value
    assert isinstance(f, (Function, PyAction)), f'expected Function or PyAction, got {f}'

    if isinstance(f, PyAction):
        args, kwargs = collect_args(f_args, scope)
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
