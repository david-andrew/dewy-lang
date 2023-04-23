from dewy import (
    AST, 
    Undefined,
    Callable,
    Orderable,
    Rangeable,
    Unpackable,
    Iter,
    Iterable,
    # BArg,
    # Scope,
    Type,
    Arg,
    Function,
    Builtin,
    Let,
    Bind,
    PackStruct,
    Unpack,
    Block,
    Call,
    String,
    IString,
    BinOp,
    Equal,
    NotEqual,
    Less,
    LessEqual,
    Greater,
    GreaterEqual,
    Add,
    Sub,
    # Mul,
    # Div,
    Bool,
    If,
    Loop,
    In,
    Next,
    Number,
    Range,
    RangeIter,
    Vector,
)
from tokenizer import tokenize, tprint, Token, Block_t, WhiteSpace_t

import pdb







from dewy import (
    hello,
    hello_func,
    anonymous_func,
    hello_name,
    if_else,
    if_else_if,
    hello_loop,
    unpack_test,
    range_iter_test,
    loop_iter_manual,
    loop_in_iter,
    nested_loop,
    block_printing,
)


funcs = [hello,
    hello_func,
    anonymous_func,
    hello_name,
    if_else,
    if_else_if,
    hello_loop,
    unpack_test,
    range_iter_test,
    loop_iter_manual,
    loop_in_iter,
    nested_loop,
    block_printing
]
from dewy import Scope
for func in funcs:
    src = func.__doc__
    tokens = tokenize(src)
    ast = func(Scope.default())
    print(f'''
-------------------------------------------------------
SRC:```{src}```
TOKENS:
{tokens}

AST:
{repr(ast)}
-------------------------------------------------------
''')

exit(1)









#TODO: precedence sorting...

# def eat_expr(tokens:list[Token]) -> AST | None:
#     """
#     eats the smallest next expression

#     id | number | ... | TODO
#     """

# def eat_call(tokens:list[Token]) -> AST | None:
#     """
#     expr(<args_list>)
#     """
#     expr = eat_expr(tokens)

def id_call(tokens:list[Token]) -> tuple[AST, list[Token]] | None:
    """
    #id #arg_list?
    """
    pdb.set_trace()


#TODO:
#def arg_call... any expression followed by () with zero or more args

def strip_whitespace(tokens:list[Token], left=True, right=True) -> list[Token]:
    """remove whitespace tokens from the left and/or right of a list of tokens"""
    if left:
        while len(tokens) > 0 and isinstance(tokens[0], WhiteSpace_t):
            tokens = tokens[1:]
    if right:
        while len(tokens) > 0 and isinstance(tokens[-1], WhiteSpace_t):
            tokens = tokens[:-1]
    return tokens

def parse(tokens:list[Token]) -> AST:
    tokens = strip_whitespace(tokens)
    
    #TODO: for now just try to match an id_call, e.g. print("hello world")
    res = id_call(tokens)

    if res is None:
        raise ValueError(f"ERROR: parse failed, no ASTs found. Tokens: {tokens}")
    
    ast, rest = res
    if len(rest) > 0:
        raise ValueError(f"ERROR: parse failed, tokens left over: {rest}")

    return ast



def test():
    import sys

    try:
        path = sys.argv[1]
    except IndexError:
        raise ValueError("Usage: `python parser.py path/to/file.dewy>`")


    with open(path) as f:
        src = f.read()

    tokens = tokenize(src)
    print(f'matched tokens:')
    tprint(Block_t(left='{', right='}', body=tokens))

    ast = parse(tokens)
    print(f'parsed ast:')
    ...



if __name__ == "__main__":
    test()