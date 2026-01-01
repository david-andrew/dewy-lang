"""
Post processing steps on tokens to prepare them for expression parsiing
"""

from dataclasses import dataclass
from .reporting import SrcFile, ReportException
from . import t1

# various juxtapose operators, for handling precedence in cases known at tokenization time
@dataclass
class Juxtapose(t1.InedibleToken2): ...

@dataclass
class RangeJuxtapose(Juxtapose): ...

@dataclass
class EllipsisJuxtapose(Juxtapose): ...

@dataclass
class BackticksJuxtapose(Juxtapose): ...

@dataclass
class TypeParamJuxtapose(Juxtapose): ...


# tokens that can be juxtaposed with each other
# note: operators and keywords do not participate in juxtaposition
juxtaposable = {
    t1.Real,
    t1.String,
    t1.Block,
    t1.BasedString,
    t1.BasedArray,
    t1.Identifier,
    t1.Handle,
    t1.Hashtag,
    t1.Integer,
}

def is_dotdot(token: t1.Token) -> bool:
    return isinstance(token, t1.Identifier) and token.name == '..'
def is_dotdotdot(token: t1.Token) -> bool:
    return isinstance(token, t1.Identifier) and token.name == '...'
def is_backticks(token: t1.Token) -> bool:
    return isinstance(token, t1.Identifier) and token.name == '`'
def is_typeparam(token: t1.Token) -> bool:
    return isinstance(token, t1.Block) and token.delims == '<>'

def get_jux_type(left: t1.Token, right: t1.Token, prev: t1.Token|None) -> type[Juxtapose]:
    if is_dotdot(left) or is_dotdot(right):
        return RangeJuxtapose
    elif is_dotdotdot(left) or is_dotdotdot(right):
        return EllipsisJuxtapose
    elif is_backticks(left) or is_backticks(right):
        return BackticksJuxtapose
    elif is_typeparam(right) or (is_typeparam(left) and not isinstance(prev, TypeParamJuxtapose)):
        return TypeParamJuxtapose
    return Juxtapose



def invert_whitespace(tokens: list[t1.Token]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)
    TODO: currently a pretty inefficient implementation. consider some type of e.g. heap or rope or etc. data structure if needed

    Args:
        tokens (list[Token]): list of tokens to modify. This is modified in place.
    """

    i = 0
    while i < len(tokens):
        # delete whitespace if it comes up
        if isinstance(tokens[i], t1.Whitespace):
            tokens.pop(i)
            continue
    
        # recursively handle inverting whitespace for blocks
        if isinstance(tokens[i], t1.Block):
            invert_whitespace(tokens[i].inner)
        elif isinstance(tokens[i], t1.IString):
            for child in tokens[i].content:
                if isinstance(child, t1.Block):
                    invert_whitespace(child.inner)
        

        # insert juxtapose if no whitespace between tokens
        if i + 1 < len(tokens) and type(tokens[i]) in juxtaposable and type(tokens[i+1]) in juxtaposable:
            jux_type = get_jux_type(tokens[i], tokens[i+1], tokens[i-1] if i > 0 else None)
            tokens.insert(i+1, jux_type(t1.Span(tokens[i].loc.stop, tokens[i].loc.stop)))
            i += 1

        # move to next token
        i += 1

        

def postok(srcfile: SrcFile) -> list[t1.Token]:
    """apply postprocessing steps to the tokens"""
    tokens = t1.tokenize2(srcfile)
    postok_inner(tokens)
    return tokens


def postok_inner(tokens: list[t1.Token]) -> None:
    """apply postprocessing steps to the tokens"""
    # remove whitespace and insert juxtapose tokens
    invert_whitespace(tokens)

    # TODO: this/these might be handled in t1 via Opchain.eat. opchains don't need to deal with juxtapose
    # # combine operator chains into a single operator token
    # make_chain_operators(tokens)
    # # convert any . operator next to a binary operator or opchain (e.g. .+ .^/-) into a broadcast operator
    # make_broadcast_operators(tokens)
    # # convert any combined assignment operators (e.g. += -= etc.) into a single token
    # make_combined_assignment_operators(tokens)

    # # bundle up conditionals into single token expressions
    # bundle_conditionals(tokens)


def test():
    from ..myargparse import ArgumentParser
    from .t0 import tokens_to_report # mildly hacky but Token2's duck-type to what this expects
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    try:
        tokens3 = postok(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    print(tokens_to_report(tokens3, srcfile))

if __name__ == '__main__':
    test()