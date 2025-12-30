"""
Post processing steps on tokens to prepare them for expression parsiing
"""

from dataclasses import dataclass
from . import t2
from . import tokenizer as t1


@dataclass
class Juxtapose(t2.InedibleToken2): ...

def invert_whitespace(tokens: list[t2.Token2]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)

    Args:
        tokens (list[Token]): list of tokens to modify. This is modified in place.
    """

    i = 0
    while i < len(tokens):
        # delete whitespace if it comes up
        if isinstance(tokens[i], t2.Whitespace):
            tokens.pop(i)
            continue
    
        # recursively handle inverting whitespace for blocks
        if isinstance(tokens[i], t2.Block):
            invert_whitespace(tokens[i].body)
        elif isinstance(tokens[i], t2.IString):
            for child in tokens[i].content:
                if isinstance(child, t2.Block):
                    invert_whitespace(child.body)
        

        # insert juxtapose if no whitespace between tokens
        if i + 1 < len(tokens) and not isinstance(tokens[i + 1], t2.Whitespace):
            tokens.insert(i+1, Juxtapose(t2.Span(tokens[i].loc.stop, tokens[i].loc.stop)))
            i += 1

        # move to next token
        i += 1

        
