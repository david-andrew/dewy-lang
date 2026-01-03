"""
Post processing steps on tokens to prepare them for expression parsiing
"""
from typing import Callable
from dataclasses import dataclass
from .reporting import SrcFile, ReportException, Span
from . import t1

# various juxtapose operators, for handling precedence in cases known at tokenization time
@dataclass
class Juxtapose(t1.InedibleToken): ...

@dataclass
class RangeJuxtapose(Juxtapose): ...

@dataclass
class EllipsisJuxtapose(Juxtapose): ...

@dataclass
class BackticksJuxtapose(Juxtapose): ...

@dataclass
class TypeParamJuxtapose(Juxtapose): ...

@dataclass
class PrefixChain(t1.InedibleToken):
    chain: list[t1.Operator]  # must be a list of unary prefix operators

@dataclass
class BinopChain(t1.InedibleToken):
    start: t1.Operator
    chain: PrefixChain

@dataclass
class BroadcastOp(t1.InedibleToken):
    op: t1.Operator | BinopChain  # must be a binary operator or an opchain
    # unary broadcasts don't seem like a coherent concept, so ignore them for now.

@dataclass
class CombinedAssignmentOp(t1.InedibleToken):
    op: t1.Operator | BinopChain | BroadcastOp   # must be a binary operator or a binary opchain or a broadcast operator

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

binary_ops: set[str] = {
    '+', '-', '*', '/', '//', '^',
    '\\',
    '=?', '>?', '<?', '>=?', '<=?', 'in?', 'is?', 'isnt?', '<=>',
    '|', '&', '??',
    '=', '::', ':=',
    '@?',
    '|>', '<|', '=>',
    '->', '<->',
    '.', ',', ':', ':>',
    '<<', '>>', '<<<', '>>>', '<<!', '!>>',
    'and', 'or', 'xor', 'nand', 'nor', 'xnor',
    'as', 'in', 'transmute', 'of', 'mod',
}
prefix_ops: set[str] = {
    '~',
    '+', '-', '*', '/', '//',
    'not',
}

# simple checks for it t1.Operator
def is_binary_op(token: t1.Token) -> bool:
    return isinstance(token, t1.Operator) and token.symbol in binary_ops
def is_prefix_op(token: t1.Token) -> bool:
    return isinstance(token, t1.Operator) and token.symbol in prefix_ops

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


def recurse_into(token: t1.Token, func: Callable[[list[t1.Token]], None]) -> None:
    """Helper to recursively apply a function to the inner tokens of a token (if it has any)"""
    if isinstance(token, t1.Block):
        func(token.inner)
    elif isinstance(token, t1.IString):
        for child in token.content:
            recurse_into(child, func)
    # TBD if other tokens may have inner tokens


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
        recurse_into(tokens[i], invert_whitespace)

        # insert juxtapose if no whitespace between tokens
        if i + 1 < len(tokens) and type(tokens[i]) in juxtaposable and type(tokens[i+1]) in juxtaposable:
            jux_type = get_jux_type(tokens[i], tokens[i+1], tokens[i-1] if i > 0 else None)
            tokens.insert(i+1, jux_type(t1.Span(tokens[i].loc.stop, tokens[i].loc.stop)))
            i += 1

        # move to next token
        i += 1



def make_chain_operators(tokens: list[t1.Token]) -> None:
    """Convert consecutive operator tokens into a single opchain token"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_chain_operators)
        
        if is_binary_op(token) or (i == 0 and is_prefix_op(token)):
            j = 1
            while i+j < len(tokens) and is_prefix_op(tokens[i+j]):
                j += 1
            if j > 1:
                # Note about distinguishing operators that could be unary or binary:
                # basically if it could be both, treat it as binary unless its the first token (which means it must be unary)
                if is_binary_op(token) and i > 0 and not isinstance(tokens[i-1], t1.Semicolon): # semicolon is a special case that ends the previous expression
                    prefix_chain = PrefixChain(Span(tokens[i+1].loc.start, tokens[i+j-1].loc.stop), tokens[i+1:i+j])
                    tokens[i:i+j] = [BinopChain(Span(tokens[i].loc.start, tokens[i+j-1].loc.stop), token, prefix_chain)]
                else:
                    tokens[i:i+j] = [PrefixChain(Span(tokens[i].loc.start, tokens[i+j-1].loc.stop), tokens[i:i+j])]
        i += 1



def make_broadcast_operators(tokens: list[t1.Token]) -> None:
    """Convert any . operator next to a binary operator or opchain into a broadcast operator"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_broadcast_operators)
        
        if isinstance(token, t1.Operator) and token.symbol == '.':
            if len(tokens) > i+1 and (is_binary_op(tokens[i+1]) or is_prefix_op(tokens[i+1]) or isinstance(tokens[i+1], BinopChain)):
                tokens[i:i+2] = [BroadcastOp(Span(token.loc.start, tokens[i+1].loc.stop), tokens[i+1])]
        i += 1


def make_combined_assignment_operators(tokens: list[t1.Token]) -> None:
    """Convert any combined assignment operators into a single token"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_combined_assignment_operators)
        
        if is_binary_op(token) or isinstance(token, BinopChain) or isinstance(token, BroadcastOp):
            if len(tokens) > i+1 and isinstance(tokens[i+1], t1.Operator) and tokens[i+1].symbol == '=':
                tokens[i:i+2] = [CombinedAssignmentOp(Span(token.loc.start, tokens[i+1].loc.stop), tokens[i+1])]
        i += 1

def bundle_conditionals(tokens: list[t1.Token]) -> None:
    raise NotImplementedError("bundle_conditionals not implemented")

def postok(srcfile: SrcFile) -> list[t1.Token]:
    """apply postprocessing steps to the tokens"""
    tokens = t1.tokenize(srcfile)
    postok_inner(tokens)
    return tokens


def postok_inner(tokens: list[t1.Token]) -> None:
    """apply postprocessing steps to the tokens"""
    # remove whitespace and insert juxtapose tokens
    invert_whitespace(tokens)

    # combine operator chains into a single operator token
    make_chain_operators(tokens)
    # convert any . operator next to a binary operator or opchain (e.g. .+ .^/-) into a broadcast operator
    make_broadcast_operators(tokens)
    # convert any combined assignment operators (e.g. += -= etc.) into a single token
    make_combined_assignment_operators(tokens)

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
        tokens = postok(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    print(tokens_to_report(tokens, srcfile))

if __name__ == '__main__':
    test()