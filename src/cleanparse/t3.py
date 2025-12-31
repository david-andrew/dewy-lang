"""
Post processing steps on tokens to prepare them for expression parsiing
"""

from dataclasses import dataclass
from .reporting import Span, SrcFile, Info, Error, Pointer, ReportException
from . import t2
from . import tokenizer as t1

# various juxtapose operators, for handling precedence in cases known at tokenization time
@dataclass
class Juxtapose(t2.InedibleToken2): ...

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
    t2.Real,
    t2.String,
    t2.Block,
    t2.BasedString,
    t2.BasedArray,
    t2.Identifier,
    t2.Handle,
    t2.Hashtag,
    t2.Integer,
}

def is_dotdot(token: t2.Token2) -> bool:
    return isinstance(token, t2.Identifier) and token.name == '..'
def is_dotdotdot(token: t2.Token2) -> bool:
    return isinstance(token, t2.Identifier) and token.name == '...'
def is_backticks(token: t2.Token2) -> bool:
    return isinstance(token, t2.Identifier) and token.name == '`'
def is_typeparam(token: t2.Token2) -> bool:
    return isinstance(token, t2.Block) and token.delims == '<>'

def get_jux_type(left: t2.Token2, right: t2.Token2, prev: t2.Token2|None) -> type[Juxtapose]:
    if is_dotdot(left) or is_dotdot(right):
        return RangeJuxtapose
    elif is_dotdotdot(left) or is_dotdotdot(right):
        return EllipsisJuxtapose
    elif is_backticks(left) or is_backticks(right):
        return BackticksJuxtapose
    elif is_typeparam(right) or (is_typeparam(left) and not isinstance(prev, TypeParamJuxtapose)):
        return TypeParamJuxtapose
    return Juxtapose



def invert_whitespace(tokens: list[t2.Token2]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)
    TODO: currently a pretty inefficient implementation. consider some type of e.g. heap or rope or etc. data structure if needed

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
            invert_whitespace(tokens[i].inner)
        elif isinstance(tokens[i], t2.IString):
            for child in tokens[i].content:
                if isinstance(child, t2.Block):
                    invert_whitespace(child.inner)
        

        # insert juxtapose if no whitespace between tokens
        if i + 1 < len(tokens) and type(tokens[i]) in juxtaposable and type(tokens[i+1]) in juxtaposable:
            jux_type = get_jux_type(tokens[i], tokens[i+1], tokens[i-1] if i > 0 else None)
            tokens.insert(i+1, jux_type(t2.Span(tokens[i].loc.stop, tokens[i].loc.stop)))
            i += 1

        # move to next token
        i += 1

        

def postok(srcfile: SrcFile) -> list[t2.Token2]:
    """apply postprocessing steps to the tokens"""
    tokens = t2.tokenize2(srcfile)
    postok_inner(tokens)
    return tokens


def postok_inner(tokens: list[t2.Token2]) -> None:
    """apply postprocessing steps to the tokens"""
    invert_whitespace(tokens)
    # TODO: other steps in the process


def test():
    from ..myargparse import ArgumentParser
    from .tokenizer import tokens_to_report # mildly hacky but Token2's duck-type to what this expects
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