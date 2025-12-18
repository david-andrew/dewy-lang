"""
t2 is the second phase of tokenization. Mainly building up a few types of compound tokens out of constituent parts. Namely:
- strings
- floats
- blocks
- opchains

Additionally symbols are separated into operators and identifiers. And identifiers from the previous step have keywords and keyword operators split off
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import groupby
from .reporting import Span, SrcFile, Error, Pointer
from . import tokenizer as t1
from .utils import JumpableIterator
from typing import Literal

import pdb

keywords: set[str] = {
    'loop', 'do', 'if', 'else', 'match', 'return', 'yield', 'break', 'continue',
    'import', 'from', 'let', 'const', 'local_const', 'fixed_type',
    # 'extern', 'intrinsic', 'undefined', 'void', 'untyped', 'end', 'new' #TBD if these are keywords or just special identifiers
}

# tokenized as symbols, but are treated as identifiers (rather than operators)
symbolic_identifiers: set[str] = {
    '?', '..', '...', '∞', '∅',  # tbd about backticks '`' which are the roll operator. need a good way to track what side of the expression they attach to (or ambiguous if touch left and right)
}

escape_map: dict[str, str] = {
    'n': '\n',
    '\n': '', # escaping a literal newline results in skipping the newline
    'r': '\r',
    't': '\t',
    'v': '\v',
    'f': '\f',
    'b': '\b',
    'a': '\a',
    '0': '\0',
}

@dataclass
class Context:
    srcfile: SrcFile

@dataclass
class Token2(ABC):
    loc: Span

    @staticmethod
    @abstractmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Token2]|None': ...

@dataclass
class Float(Token2):
    """
    Patterns:
    3.14
    1.0
    1.23e4
    1.23E+4
    1.23e-4
    0x1.8p10    % note `p` instead of `e` for exponent. 0x1.8p10 = 1.5 × 2¹⁰
    0x1.fp-2    % bug: if number after dot is different base, tokenizer doesn't recognize it without a prefix.. perhaps make that the case (i.e. require user to specify prefix every time, warn if bases don't match in float)
    1e10
    2E-23

    10.25p3  % all base 10. suggested to either warn or error (leaning warn b/c simpler to parse, just look for src[i] in 'eEpP')

    0x1.0x8p10   % special case <hex>.<hex>p<dec> gets no warning, even though base mismatch
    0x1.0x8p0xA  % no warning, though programmer being extra explicit
    0x1.0b1p10   % warn, mantissa halves have different bases
    0x1.8p10     % warn, different bases
    
    p/P is only allowed for bases that are powers of 2, and means 2^exponent (instead of 10^exponent for e/E)

    literals? probably not parsed here, but as identifiers
      nan
      inf
    literals are treated as singleton types, and receive their bit pattern when used in a typed context
    ```dewy
    a:float64 = inf  % convert to ieee754 compatible float inf
    b:int = inf`     % convert to symbolic InfinityType that can interact with ints as a singleton type
    ```

    suggested to have some set of string input functions for C/IEEE-754 notation
    ieee754<float64>'0x1.8p10'
    """
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Float]|None':
        raise NotImplementedError()

@dataclass
class String(Token2):
    content: str

    """
    any strings that contain only chars and or non-parametric escapes (i.e. the entire string is known and can be rendered without evaluating any interpolations or parametric escape expressions)


    <string_inner> = (chars|escape|block)*

    string = 
      | <quote><string_inner><quote>
      | <raw_quote><chars>*<quote>
      | <heredoc_start><string_inner><heredoc_end>
      | <raw_heredoc_start><chars>*<heredoc_end>
      | <rof_start><chars>*
    
    perhaps consider two separate string tokens:
    - interpolated
    - chars only
    we would select the appropriate one based on if there are any blocks present in the string
    (perhaps later in type checking, some interpolated strings could be converted to chars only if their expression is compiletime const)
    """
    # potentially find a way for IString to share this logic, since it's just a matter of checking what was in the string body
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, String]|None':
        opener = tokens[start]
        if isinstance(opener, (t1.StringQuoteOpener, t1.RawStringQuoteOpener, t1.HeredocStringOpener, t1.RawHeredocStringOpener)):
            body_start, body_stop = start + 1, opener.matching_quote.idx
            span = Span(opener.loc.start, opener.matching_quote.loc.stop)
            eaten = body_stop - body_start + 2  # body len + 2 quotes
        elif isinstance(opener, t1.RestOfFileStringQuote):
            body_start, body_stop = start + 1, len(tokens) - 1
            span = Span(opener.loc.start, tokens[-1].loc.stop)
            eaten = len(tokens) - body_start + 1  # body len + just 1 opening quote
        else:
            # current tokens aren't a string
            return None
        
        content = String.body_to_string(tokens, ctx, body_start, body_stop)

        # Regular String if all content is string, else IString for strings that contain any interpolations
        if isinstance(content, str):
            return eaten, String(span, content)
        return eaten, IString(span, content)

    @staticmethod
    def get_escape_char(escape: t1.StringEscape) -> str:
        if escape.src[1:] in escape_map:
            return escape_map[escape.src[1:]]
        elif escape.src[1] in 'uU':
            assert len(escape.src) == 6, f'INTERNAL ERROR: Invalid unicode escape sequence: {escape.src}'
            return chr(int(escape.src[2:], 16))
        else:
            assert len(escape.src) == 2, f'INTERNAL ERROR: Invalid escape sequence: {escape.src}'
            return escape.src[1] # all other escapes are just the literal next character

    @staticmethod
    def body_to_string(tokens: list[t1.Token], ctx:Context, body_start:int, body_stop:int) -> 'str|list[str|ParametricEscape|Block]':
        chunks = []
        token_iter = JumpableIterator(tokens, body_start, body_stop)
        for token in token_iter:
            if isinstance(token, (t1.StringChars, t1.RawStringChars)):
                chunks.append(token.src)
            elif isinstance(token, t1.StringEscape):
                chunks.append(String.get_escape_char(token))
            elif isinstance(token, t1.ParametricStringEscape):
                raise NotImplementedError(f'parametric escapes not implemented yet')
                #needs to process all the inner tokens of the block
            elif isinstance(token, t1.LeftCurlyBrace):
                if token.matching_right.idx - token.idx == 1:
                    error = Error(
                        srcfile=ctx.srcfile,
                        title=f'Empty interpolation block',
                        pointer_messages=[
                            Pointer(span=Span(token.loc.start, token.matching_right.loc.stop), message=f'Empty interpolation block'),
                        ],
                        hint=f'Interpolation blocks must contain at least one token.\nIf you meant `{{}}` literally, use an escape, e.g. `\\{{}}`'
                    )
                    error.throw()
                inner = tokenize2_inner(tokens, ctx, token.idx+1, token.matching_right.idx)
                chunks.append(Block(Span(token.loc.start, token.matching_right.loc.stop), inner, '{}'))
                token_iter.jump_forward(token.matching_right.idx - token.idx + 1) # skip inner tokens and closing brace
            else:
                pdb.set_trace()
                #unreachable
                raise ValueError(f'INTERNAL ERROR: Invalid token in string body: {token}')
        
        if all(isinstance(t, str) for t in chunks):
            return ''.join(chunks)
        
        # combine any adjacent strings into a single string
        combined = []
        for is_str, group in groupby(chunks, key=lambda x: isinstance(x, str)):
            if is_str: combined.append(''.join(group))
            else: combined.extend(group)
        
        return combined

@dataclass
class ParametricEscape(Token2): ...

@dataclass
class IString(Token2):
    content: 'list[str | ParametricEscape | Block]'
    """
    Any string that contains an expression or interpolation (includes parametric unicode+hex escapes)
    """
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, IString]|None':
        raise NotImplementedError('IString does not implement eat. Instead use String.eat which may return an IString if any interpolations are present')

@dataclass
class Block(Token2):
    inner: list[Token2]
    delims: Literal['{}', '[]', '()', '[)', '(]', '<>']
    """
    <opener><inner_tokens><matching closer>
    """
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Block]|None':
        raise NotImplementedError()

@dataclass
class OpChain(Token2):
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, OpChain]|None':
        raise NotImplementedError()

@dataclass
class Identifier(Token2):
    name: str

    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Identifier]|None':
        token = tokens[start]
        if isinstance(token, t1.Identifier) and token.src not in keywords:
            return 1, Identifier(token.loc, token.src)
        elif isinstance(token, t1.Symbol) and token.src in symbolic_identifiers:
            return 1, Identifier(token.loc, token.src)
        # TODO: are there any other things that are identifiers?
        
        return None

@dataclass
class Operator(Token2):
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Operator]|None':
        raise NotImplementedError()

@dataclass
class Keyword(Token2): # e.g. if, loop, import, let, etc. any keyword that behaves differently syntactically e.g. `<keyword> <expr>`. Ignore keywords that can go in identifiers, e.g. `void`, `intrinsic`/`extern`, etc.
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Keyword]|None':
        token = tokens[start]
        if isinstance(token, t1.Identifier) and token.src in keywords:
            return 1, Keyword(token.loc, token.src)
        return None

@dataclass
class Hashtag(Token2):
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Hashtag]|None':
        raise NotImplementedError()

@dataclass
class Integer(Token2):
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Integer]|None':
        raise NotImplementedError()

@dataclass
class Whitespace(Token2): # so we can invert later for juxtapose
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Whitespace]|None':
        raise NotImplementedError()

top_level_tokens: list[type[Token2]] = [
    Identifier,
    String,
    # IString,
    # ParametricEscape,
    Keyword,
    Hashtag,
    Integer,
    Float,
    Block,
    OpChain,
    Operator,
    Whitespace,
]

def tokenize2(srcfile: SrcFile) -> list[Token2]:
    """Public API for second tokenization stage"""
    tokens = t1.tokenize(srcfile)
    ctx = Context(srcfile)
    return tokenize2_inner(tokens, ctx)

def tokenize2_inner(tokens:list[t1.Token], ctx:Context, start:int=0, stop:int=None) -> list[Token2]:
    processed: list[Token2] = []
    if stop is None: stop = len(tokens)
    if stop > len(tokens): raise ValueError(f"INTERNAL ERROR: stop index out of range: {stop} > {len(tokens)}")
    while start < stop:
        for token_cls in top_level_tokens:
            res = token_cls.eat(tokens, ctx, start)
            if res is not None:
                num_eaten, token = res
                processed.append(token)
                start += num_eaten
                break
        else:
            # TODO: proper error reporting
            error = Error(
                srcfile=ctx.srcfile,
                title=f'No token found',
                pointer_messages=[
                    Pointer(span=Span(tokens[0].loc.start, tokens[0].loc.start), message=f'Unrecognized starting here'),
                ],
                hint=f'TODO: better error analysis'
            )
            error.throw()

    return processed


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
    tokens2 = tokenize2(srcfile)
    print(tokens_to_report(tokens2, srcfile))



if __name__ == '__main__':
    test()