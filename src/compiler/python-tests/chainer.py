from tokenizer import (Token, tokenize, 
    WhiteSpace_t,
    Block_t,
    TypeParam_t,
    String_t,
    Operator_t,
    ShiftOperator_t,
    Comma_t,
    Juxtapose_t
)

from enum import Enum, auto


import pdb


"""
TODO:
- full pipeline for hello world:
  [x] tokenize
  [ ] chain (still no typing, just group single expressions together)
  [ ] parse (building up types based on expressions and types of lowest levels/outside in)
"""


# There is no chain class
# A chain is just a list of tokens that is directly parsable as an expression without any other syntax
# all other syntax is wrapped up into compound tokens
# it should literally just be a sequence of atoms and operators
    



def invert_whitespace(tokens: list[Token]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)

    Args:
        tokens (list[Token]): list of tokens to modify. This is modified in place.
    """
    
    #juxtapose singleton token so we aren't wasting memory
    jux = Juxtapose_t(None)
    
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

    #finally, remove juxtapose tokens next to operators that are not whitespace sensitive
    i = 1
    while i < len(tokens) - 1:
        left,middle,right = tokens[i-1:i+2]
        if isinstance(middle, Juxtapose_t) and (isinstance(left, (Operator_t, ShiftOperator_t, Comma_t)) or isinstance(right, (Operator_t, ShiftOperator_t, Comma_t))):
            tokens.pop(i)
            continue
        i += 1





def bundle_conditionals(tokens: list[Token]) -> None:
    """Convert sequences of tokens that represent conditionals (if, loop, etc.) into a single expression token"""
    raise NotImplementedError
    #TODO: should scan through, and if it finds a conditional, raise the not implemented error

def chain_operators(tokens: list[Token]) -> None:
    """Convert consecutive operator tokens into a single opchain token"""
    raise NotImplementedError
    #TODO: should scan through, and if it finds a chain of operators, raise the not implemented error


def chain(tokens: list[Token]) -> list[list[Token]]:
    # remove whitespace, and insert juxtapose tokens
    invert_whitespace(tokens)

    # bundle up conditionals into single token expressions
    bundle_conditionals(tokens)

    # combine operator chains into a single operator token
    # TODO: skip for now. not needed by hello world
    # also may not be necessary if we use a pratt parser. was necessary for split by lowest precedence parser
    chain_operators(tokens)

    # make the actual list of chains

    # based on types, replace jux with jux_mul or jux_call
    # TODO: actually this probably would need to be done during parsing, since we can't get a type for a complex/compound expression...

    pdb.set_trace()
    ...



def test():
    with open('../../../examples/hello.dewy') as f:
        src = f.read()

    tokens = tokenize(src)
    chains = chain(tokens)

    pdb.set_trace()
    ...
    


if __name__ == '__main__':
    test()