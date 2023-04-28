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
from tokenizer import ( tokenize, tprint, traverse_tokens,
    Token, 
    WhiteSpace_t,
    Juxtapose_t,
    Identifier_t,
    Block_t,
    TypeParam_t,
    String_t,
    Integer_t,
    BasedNumber_t,

)

import pdb




valid_brace_pairs = {
    '{': '}',
    '(': ')]',
    '[': '])',
    # '<': '>'
}
def validate_block_braces(tokens:list[Token]) -> None:
    """
    Checks that all blocks have valid open/close pairs.

    For example, ranges may have differing open/close pairs, e.g. [0..10), (0..10], etc.
    But regular blocks must have matching open/close pairs, e.g. { ... }, ( ... ), [ ... ]
    Performs some validation, without knowing if the block is a range or a block. 
    So more validation is needed when the actual block type is known.

    Raises:
        AssertionError: if a block is found with an invalid open/close pair
    """
    for token in traverse_tokens(tokens):
        if isinstance(token, Block_t):
            assert token.left in valid_brace_pairs, f'INTERNAL ERROR: left block opening token is not a valid token. Expected one of {[*valid_brace_pairs.keys()]}. Got \'{token.left}\''
            assert token.right in valid_brace_pairs[token.left], f'ERROR: mismatched opening and closing braces. For opening brace \'{token.left}\', expected one of \'{valid_brace_pairs[token.left]}\''
        


jux = Juxtapose_t(None)
def invert_whitespace(tokens: list[Token]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)

    Args:
        tokens (list[Token]): list of tokens to modify. This is modified in place.
    """
    i = 0
    while i < len(tokens):
        # delete whitespace if it comes up
        if isinstance(tokens[i], WhiteSpace_t):
            tokens.pop(i)
            continue

        # recursively handle inverting whitespace for blocks
        if isinstance(tokens[i], (Block_t, TypeParam_t)):
            invert_whitespace(tokens[i].body)
        elif isinstance(tokens[i], String_t):
            for child in tokens[i].body:
                if isinstance(child, Block_t):
                    invert_whitespace(child.body)

        # insert juxtapose if no whitespace between tokens
        if i + 1 < len(tokens) and not isinstance(tokens[i + 1], WhiteSpace_t):
            tokens.insert(i + 1, jux)
            i += 1
        i += 1





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
    print('\n\n\n')

    # ensure that all blocks have valid open/close pairs
    validate_block_braces(tokens)


    # in between tokenizing and parsing
    invert_whitespace(tokens)
    tprint(Block_t(left='{', right='}', body=tokens))




    # ast = parse(tokens)
    # print(f'parsed ast: {ast}')



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
