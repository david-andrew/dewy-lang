from dataclasses import dataclass

from ..tokenizer import tokenize
from ..postok import post_process
from ..parser import top_level_parse, Scope
from ..syntax import AST, Type, undefined, untyped, void, DeclarationType
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
    return
    raise NotImplementedError("evaluation hasn't been implemented yet")

    res = top_level_evaluate(ast)
    if res and res is not void:
        print(res)



def top_level_evaluate(ast:AST) -> AST|None:
    pdb.set_trace()
    scope = Scope.default()
    return evaluate(ast, scope)

def evaluate(ast:AST, scope:Scope) -> AST|None:
    pdb.set_trace()
