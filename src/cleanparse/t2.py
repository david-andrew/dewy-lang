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
from .reporting import Span, SrcFile, Info, Error, Pointer, ReportException
from . import tokenizer as t1
from .utils import JumpableIterator
from typing import Literal, Generator

import pdb

keywords: set[str] = {
    'loop', 'do', 'if', 'else', 'match', 'return', 'yield', 'break', 'continue',
    'import', 'from', 'let', 'const', 'local_const', 'fixed_type',
    # 'extern', 'intrinsic', 'undefined', 'void', 'untyped', 'end', 'new' #TBD if these are keywords or just special identifiers
}

# tokenized as symbols, but are treated as identifiers (rather than operators)
symbolic_identifiers: set[str] = {
    '?', '..', '...', '`', '∞', '∅',
}

# tokenized as identifiers, but are treated as operators (rather than identifiers)
word_operators: set[str] = {
    'and', 'or', 'xor', 'nand', 'nor', 'xnor', 'not',
    'as', 'in', 'transmute', 'of', 'mod',
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
class InedibleToken2(Token2):
    """For Token2's that are not constructed via the normal .eat() method. instead other tokens may construct them directly"""
    @classmethod
    def eat(cls, tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, InedibleToken2]|None':
        raise NotImplementedError(f'{cls.__name__} should not be constructed via .eat(). Instead some other token should construct it directly via {cls.__name__}(...)')

@dataclass
class Exponent:
    value: t1.Number
    positive: bool=True # true for positive, false for negative, e.g. 1e-2 is positive=False
    binary: bool=False  # true when the exponent is a power of 2 (e.g. 0x1.0x8p10)

@dataclass
class Real(Token2):
    whole: t1.Number
    fraction: t1.Number|None
    exponent: Exponent|None
    
    """
    Patterns:
    <number><eEpP><number>
    <number><eEpP><+-><number>
    <number><dot><number>
    <number><dot><number><eEpP><number>
    <number><dot><number><eEpP><+-><number>

    
    Examples:
    3.14
    1.0
    1.23e4
    1.23E+4
    1.23e-4
    0x1.0x8p10  % note `p` instead of `e` for exponent. 0x1.8p10 = 1.5 × 2¹⁰
    % 0x1.fp-2  % note this won't parse as a float because no prefix was used for the number after the dot. <int 0x1><dot><identifier fp><operator -><int 2>
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
    b:int = inf      % convert to symbolic InfinityType that can interact with ints as a singleton type
    ```

    suggested to have some set of string input functions for C/IEEE-754 notation
    ieee754<float64>'0x1.8p10'
    """
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Real]|None':
        if start + 2 >= len(tokens):
            return None
        ########## Whole number part ##########
        if not isinstance(tokens[start], t1.Number):
            return None
        whole = tokens[start]

        ########## Fractional part ##########
        i = 1
        fraction = None
        if (
            start + i + 1 < len(tokens)
            and isinstance((dot:=tokens[start + i]), t1.Symbol) and dot.src == '.'
            and isinstance(tokens[start + i + 1], t1.Number)
        ):
            fraction = tokens[start + i + 1]
            i += 2
        
        ########## Exponent part ##########
        exponent = None
        # weird disambiguation case where the exponent part looked like an identifier
        if start + i < len(tokens) and isinstance(marker:=tokens[start + i], t1.ExponentMarker):
            exponent = Exponent(marker.power)
            i += 1
        # <eEpP><number>
        elif (
            start + i + 1 < len(tokens)
            and isinstance((e:=tokens[start + i]), t1.Identifier) and e.src in 'eEpP'
            and isinstance(tokens[start + i + 1], t1.Number)
        ):
            exponent = Exponent(tokens[start + i + 1], positive=True, binary=e.src in 'pP')
            i += 2
        # <eEpP><+-><number>
        elif (
            start + i + 2 < len(tokens)
            and isinstance((e:=tokens[start + i]), t1.Identifier) and e.src in 'eEpP'
            and isinstance((sign:=tokens[start + i + 1]), t1.Symbol) and sign.src in '+-'
            and isinstance(tokens[start + i + 2], t1.Number)
        ):
            exponent = Exponent(tokens[start + i + 2], positive=sign.src == '+', binary=e.src in 'pP')
            i += 3
        

        ########## Return result ##########
        # not a float unless there was at least one of these
        if fraction is None and exponent is None:
            return None
        
        span = Span(whole.loc.start, tokens[start + i - 1].loc.stop)
        return i, Real(span, whole, fraction, exponent)
        

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
        elif isinstance(opener, (t1.RestOfFileStringQuote, t1.RawRestOfFileStringQuote)):
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
                raise NotImplementedError('parametric escapes not implemented yet')
                #needs to process all the inner tokens of the block
            elif isinstance(token, t1.LeftCurlyBrace):
                if token.matching_right.idx - token.idx == 1:
                    error = Error(
                        srcfile=ctx.srcfile,
                        title='Empty interpolation block',
                        pointer_messages=[
                            Pointer(span=Span(token.loc.start, token.matching_right.loc.stop), message='Empty interpolation block'),
                        ],
                        hint='Interpolation blocks must contain at least one token.\nIf you meant `{{}}` literally, use an escape, e.g. `\\{{}}`'
                    )
                    error.throw()
                inner = list(tokenize2_gen(tokens, ctx, token.idx+1, token.matching_right.idx))
                chunks.append(Block(Span(token.loc.start, token.matching_right.loc.stop), inner, '{}'))
                token_iter.jump_forward(token.matching_right.idx - token.idx + 1) # skip inner tokens and closing brace
            else:
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
class ParametricEscape(InedibleToken2):
    block: 'Block'

@dataclass
class IString(InedibleToken2):
    """Any string that contains an expression or interpolation (includes parametric unicode+hex escapes)"""
    content: 'list[str | ParametricEscape | Block]'

@dataclass
class Block(Token2):
    inner: list[Token2]
    delims: Literal['{}', '[]', '()', '[)', '(]', '<>']
    """
    <opener><inner_tokens><matching closer>
    """
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Block]|None':
        opener = tokens[start]

        if not isinstance(opener, (t1.LeftCurlyBrace, t1.LeftParenthesis, t1.LeftSquareBracket, t1.LeftAngleBracket)):
            return None

        closer = opener.matching_right
        delims = opener.src + closer.src
        span = Span(opener.loc.start, closer.loc.stop)
        body_start, body_stop = start + 1, closer.idx
        inner = list(tokenize2_gen(tokens, ctx, body_start, body_stop))
        assert delims in ['{}', '[]', '()', '[)', '(]', '<>'], f'INTERNAL ERROR: invalid block delimiter: {delims}'
        return closer.idx - start + 1, Block(span, inner, delims)

@dataclass
class BasedString(Token2):
    digits: 'list[t1.BasedStringChars]'
    base: t1.BasePrefix
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, BasedString]|None':
        opener = tokens[start]
        if not isinstance(opener, t1.BasedStringQuoteOpener):
            return None
        
        closer = opener.matching_quote
        span = Span(opener.loc.start, closer.loc.stop)
        raw_body = tokens[opener.idx+1:closer.idx]
        digits = [token for token in raw_body if isinstance(token, t1.BasedStringChars)]
        return closer.idx - start + 1, BasedString(span, digits, opener.base)


@dataclass
class BasedArray(Token2):
    inner: 'list[Integer]'
    base: t1.BasePrefix
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, BasedArray]|None':
        opener = tokens[start]
        if not isinstance(opener, t1.BasedBlockOpener):
            return None
        
        # tokenize the inner body
        closer = opener.matching_right
        span = Span(opener.loc.start, closer.loc.stop)
        body_start, body_stop = start + 1, closer.idx
        inner = list(tokenize2_gen(tokens, ctx, body_start, body_stop))
        
        # filter out any non integers
        integers = [token for token in inner if isinstance(token, Integer)]
        
        return closer.idx - start + 1, BasedArray(span, integers, opener.base)

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
        if isinstance(token, t1.Identifier) and token.src not in keywords and token.src not in word_operators:
            return 1, Identifier(token.loc, token.src)
        elif isinstance(token, t1.Symbol) and token.src in symbolic_identifiers:
            return 1, Identifier(token.loc, token.src)
        
        return None

@dataclass
class Handle(Token2):
    identifier: Identifier

    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Handle]|None':
        """handles are strictly <@><identifier>"""
        token = tokens[start]
        if not isinstance(token, t1.Symbol) or token.src != '@':
            return None
        
        # check if an identifier follows
        res = None
        if start + 1 < len(tokens):
            res = Identifier.eat(tokens, ctx, start + 1)
        
        if res is None:
            next_token = peek_next_token(tokens, ctx, start + 1)
            error = Error(
                srcfile=ctx.srcfile,
                title='Invalid handle',
                pointer_messages=[
                    Pointer(span=token.loc, message='handle without following identifier'),
                    *([Pointer(span=next_token.loc, message=f"expected <Identifier>, got <{type(next_token).__name__}>", color='red')] if next_token is not None else []),
                ],
                hint='@ must be immediately followed by an identifier, e.g. `@my_variable`'
            )
            error.throw()
        length, identifier = res
        return length + 1, Handle(Span(token.loc.start, identifier.loc.stop), identifier)
        
        

@dataclass
class Operator(Token2):
    symbol: str

    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Operator]|None':
        token = tokens[start]

        # non-symbolic operators
        if isinstance(token, t1.Identifier) and token.src in word_operators:
            return 1, Operator(token.loc, token.src)

        # all symbols that are not symbolic identifiers are operators
        if not isinstance(token, (t1.Symbol, t1.ShiftSymbol)) or token.src in symbolic_identifiers: 
            return None
        if token.src == '@':  # @ operator is handled by Handle
            return None
        return 1, Operator(token.loc, token.src)
            

@dataclass
class Keyword(Token2): # e.g. if, loop, import, let, etc. any keyword that behaves differently syntactically e.g. `<keyword> <expr>`. Ignore keywords that can go in identifiers, e.g. `void`, `intrinsic`/`extern`, etc.
    name: str

    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Keyword]|None':
        token = tokens[start]
        if isinstance(token, t1.Identifier) and token.src in keywords:
            return 1, Keyword(token.loc, token.src)
        return None

@dataclass
class Hashtag(Token2):
    name: str
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Hashtag]|None':
        token = tokens[start]
        if isinstance(token, t1.Hashtag):
            return 1, Hashtag(token.loc, token.src[1:])
        return None

@dataclass
class Integer(Token2):
    value: t1.Number
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Integer]|None':
        token = tokens[start]
        if isinstance(token, t1.Number):
            return 1, Integer(token.loc, token)
        return None

@dataclass
class Whitespace(Token2): # so we can invert later for juxtapose
    @staticmethod
    def eat(tokens:list[t1.Token], ctx:Context, start:int) -> 'tuple[int, Whitespace]|None':
        i = 0
        while start + i < len(tokens) and isinstance(tokens[start + i], (t1.Whitespace, t1.LineComment, t1.BlockComment)):
            i += 1
        if i == 0: return None
        return i, Whitespace(Span(tokens[start].loc.start, tokens[start + i - 1].loc.stop))

top_level_tokens: list[type[Token2]] = [
    Identifier,
    Handle,
    String,
      # IString,           # not included in top level tokens because created by String.eat
      # ParametricEscape,  # not included in top level tokens because created by String.eat
    Keyword,
    Hashtag,
    Integer,
    Real,
    Block,
    BasedString,
    BasedArray,
    # OpChain,
    Operator,
    Whitespace,
]

def tokenize2(srcfile: SrcFile) -> list[Token2]:
    """Public API for second tokenization stage"""
    tokens = t1.tokenize(srcfile)
    ctx = Context(srcfile)
    return list(tokenize2_gen(tokens, ctx))

def tokenize2_gen(tokens:list[t1.Token], ctx:Context, start:int=0, stop:int=None) -> Generator[Token2, None, None]:
    # processed: list[Token2] = []
    if stop is None: stop = len(tokens)
    if stop > len(tokens): raise ValueError(f"INTERNAL ERROR: stop index out of range: {stop} > {len(tokens)}")
    while start < stop:
        matches = [token_cls.eat(tokens, ctx, start) for token_cls in top_level_tokens]
        matches = list(filter(None, matches))
        if len(matches) == 0:
            # TODO: more specific error reporting based on the case
            error = Error(
                srcfile=ctx.srcfile,
                title='No token found',
                pointer_messages=[
                    Pointer(span=Span(tokens[start].loc.start, tokens[start].loc.start), message='Unrecognized starting here'),
                ],
                hint='TODO: better error analysis'
            )
            error.throw()
        if len(matches) > 1:
            # try for longest match, otherwise probably ambiguous error
            longest_match_length = max(length for length, _ in matches)
            matches = [(match_length, token) for match_length, token in matches if match_length == longest_match_length]
            if len(matches) > 1:
                # TODO: more specific error reporting based on the case
                error = Error(
                    srcfile=ctx.srcfile,
                    title='Multiple tokens matched',
                    pointer_messages=[
                        Pointer(span=Span(tokens[start].loc.start, tokens[start].loc.start), message='Multiple tokens matched'),
                    ],
                    hint=f'The following tokens matched: {matches}\nTODO: provide better explanation for how to disambiguate'
                )
                error.throw()
    
        match_length, token = matches[0]
        # processed.append(token)
        yield token
        start += match_length

    # return processed


def peek_next_token(tokens:list[t1.Token], ctx:Context, start:int) -> 'Token2|t1.Token|None':
    """Mostly for error reporting purposes. Try to get the next token2. Otherwise try to get the next token1. Otherwise return None"""
    if start >= len(tokens):
        return None
    try:
        return next(tokenize2_gen(tokens, ctx, start, len(tokens)))
    except Exception:
        if start < len(tokens):
            return tokens[start]
        return None


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
        tokens2 = tokenize2(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)

    print(tokens_to_report(tokens2, srcfile, {Whitespace}))

if __name__ == '__main__':
    test()