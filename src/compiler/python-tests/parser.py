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
from tokenizer import ( tokenize, tprint,
    Token, 
    WhiteSpace_t,
    Identifier_t,
    Block_t,
    String_t,
    Integer_t,
    BasedNumber_t,
)

import pdb



#expression chains
# build chain one token at a time, decide if it is part of the current expression chain
# once chain is built, split by lowest precedence operator (kept track of during chain building)
# create the node for the operator, and semi-recurse process on the left and right halves 
#  - (the chain already exists, just need to find the lowest precedence operator)


# TODO: these should include an optional validator function that either runs after a candidate was successful (or perhaps after each token that passes...)
expression_templates: list[tuple[type, list[type]]] = [
    (None, (Identifier_t,)),
    (None, (Integer_t,)),
    (None, (BasedNumber_t,)),
    (None, (String_t,)),
    (Call, (..., Block_t)),
]



def progress_chain(token:Token, candidate:tuple[int, type, list[type]]) -> tuple[int, type, list[type]]|None:
    #unpack candidate
    i, ast_type, template = candidate

    assert i < len(template), f"ERROR: progress_chain called on a completed chain: {candidate}"
    
    if token.__class__ is template[i]:
        return (i+1, ast_type, template)

    return None

def get_initial_candidates(current_chain:list) -> list[tuple[type, list[type]]]:
    candidates = []
    
    for ast_type, template in expression_templates:
        if template[0] is ... and len(current_chain) > 0:
            candidates.append((1, ast_type, template))
        elif template[0] is not ...:
            candidates.append((0, ast_type, template))
    return candidates


def parse(tokens:list[Token]) -> AST:
    """
    parse a list of tokens into an AST
    """
    
    chains = []
    current_chain = []
    prev_was_whitespace = False
    while len(tokens) > 0:
        
        chunk_tokens = []
        #TODO: lowest_precedence_op = ... # or just keep track of the indices of all operators in the chain?
        candidates = get_initial_candidates(current_chain)
        
        while len(tokens) > 0:

            #skip leading whitespace
            if isinstance(tokens[0], WhiteSpace_t):
                tokens = tokens[1:]
                prev_was_whitespace = True
                continue

            token, tokens = tokens[0], tokens[1:]
            chunk_tokens.append(token)
            print(f'token: {token}')
            print(f'chunk_tokens: {chunk_tokens}')
            print(f'current_chain: {current_chain}')
            print(f'candidates: {candidates}')

            #progress all candidates and remove any that are None
            candidates = [progress_chain(token, c) for c in candidates]
            candidates = [c for c in candidates if c is not None]

            #separate out completed candidates
            completed = [c for c in candidates if c[0] == len(c[2])]
            candidates = [c for c in candidates if c[0] != len(c[2])]

            #validate any completed candidates
            #TODO

            assert len(completed) <= 1, f"ERROR: multiple candidates completed at the same time: {completed}"

            # indicate that the previous token was not whitespace
            prev_was_whitespace = False

            if len(completed) == 1:
                #add the completed candidate to the chain
                i, ast_type, template = completed[0]
                current_chain.append((ast_type, template, chunk_tokens))
                break
            
            if len(candidates) == 0:
                #no candidates left, break out of the loop
                #TODO: perhaps this means the end of the current chain (but more tokens/chains follow)?
                raise ValueError(f"ERROR: no candidates left: {chunk_tokens=}")
            
    pdb.set_trace()
    ...







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

# def id_call(tokens:list[Token]) -> tuple[AST, list[Token]] | None:
#     """
#     #id #arg_list?
#     """
#     pdb.set_trace()


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


# def parse(tokens:list[Token]) -> AST:
#     tokens = strip_whitespace(tokens)
    
#     #TODO: for now just try to match an id_call, e.g. print("hello world")
#     res = id_call(tokens)

#     if res is None:
#         raise ValueError(f"ERROR: parse failed, no ASTs found. Tokens: {tokens}")
    
#     ast, rest = res
#     if len(rest) > 0:
#         raise ValueError(f"ERROR: parse failed, tokens left over: {rest}")

#     return ast



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
    print(f'parsed ast: {ast}')



if __name__ == "__main__":
    test()







# from dewy import (
#     hello,
#     hello_func,
#     anonymous_func,
#     hello_name,
#     if_else,
#     if_else_if,
#     hello_loop,
#     unpack_test,
#     range_iter_test,
#     loop_iter_manual,
#     loop_in_iter,
#     nested_loop,
#     block_printing,
# )


# funcs = [hello,
#     hello_func,
#     anonymous_func,
#     hello_name,
#     if_else,
#     if_else_if,
#     hello_loop,
#     unpack_test,
#     range_iter_test,
#     loop_iter_manual,
#     loop_in_iter,
#     nested_loop,
#     block_printing
# ]
# from dewy import Scope
# for func in funcs:
#     src = func.__doc__
#     tokens = tokenize(src)
#     ast = func(Scope.default())
#     print(f'''
# -------------------------------------------------------
# SRC:```{src}```
# TOKENS:
# {tokens}

# AST:
# {repr(ast)}
# -------------------------------------------------------
# ''')

# exit(1)
