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
from .reporting import Span, SrcFile
from . import tokenizer as t1
from .utils import index_of


import pdb

keywords: set[str] = {
    'loop', 'do', 'if', 'else', 'match', 'return', 'yield', 'break', 'continue',
    'import', 'from', 'let', 'const', 'local_const', 'fixed_type',
    # 'extern', 'intrinsic', 'undefined', 'void', 'untyped', 'end', 'new' #TBD if these are keywords or just special identifiers
}

# tokenized as symbols, but are treated as identifiers (rather than operators)
symbolic_identifiers: set[str] = {
    '?', '..', '...', '∞', '∅'
}

escape_map: dict[str, str] = {
    'n': '\n',
    'r': '\r',
    't': '\t',
    'v': '\v',
    'f': '\f',
    'b': '\b',
    'a': '\a',
    '0': '\0',
}

@dataclass
class Token2(ABC):
    loc: Span

    @staticmethod
    @abstractmethod
    def eat(tokens:list[t1.Token]) -> 'Token2|None': ...

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
    def eat(tokens:list[t1.Token]) -> 'Float|None':
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
    def eat(tokens:list[t1.Token]) -> 'String|None':
        if isinstance(tokens[0], t1.StringQuoteOpener):
            opener = tokens[0]
            i = index_of(opener.matching_quote, tokens)
            assert i is not None, f"INTERNAL ERROR: no matching quote found for {opener}"
            span = Span(opener.loc.start, opener.matching_quote.loc.stop)
            body = tokens[1:i]
            del tokens[:i+1]
            if not all(isinstance(t, (t1.StringChars, t1.StringEscape)) for t in body):
                return IString.from_body(span, body)
            # build a single string for the String token
            chunks = []
            for t in body:
                if isinstance(t, t1.StringChars):
                    chunks.append(t.src)
                elif isinstance(t, t1.StringEscape):
                    if t.src[1:] in escape_map:
                        chunks.append(escape_map[t.src[1:]])
                    elif t.src.startswith('\\x') or t.src.startswith('\\X'):
                        assert len(t.src) == 4, f'INTERNAL ERROR: Invalid hex escape sequence: {t.src}'
                        chunks.append(chr(int(t.src[2:], 16)))
                    elif t.src.startswith('\\u') or t.src.startswith('\\U'):
                        assert len(t.src) == 6, f'INTERNAL ERROR: Invalid unicode escape sequence: {t.src}'
                        raise NotImplementedError(f'Unicode escapes are not supported yet, (because have to figure out how to handle string encoding)')
                        ...
                    else:
                        assert len(t.src) == 2, f'INTERNAL ERROR: Invalid escape sequence: {t.src}'
                        chunks.append(t.src[1]) # all other escapes are just the literal next character

            return String(span, ''.join(chunks))
            ...
        pdb.set_trace()
        ...

class ParametricEscape(Token2): ...
class IString(Token2):
    content: 'list[str | ParametricEscape | Block]'
    """
    Any string that contains an expression or interpolation (includes parametric unicode+hex escapes)
    """
    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'IString|None':
        raise NotImplementedError()

class Block(Token2):
    """
    <opener><inner_tokens><matching closer>
    """
    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'Block|None':
        raise NotImplementedError()

class OpChain(Token2):
    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'OpChain|None':
        raise NotImplementedError()

@dataclass
class Identifier(Token2):
    name: str

    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'Identifier|None':
        if isinstance(tokens[0], t1.Identifier) and tokens[0].src not in keywords:
            token = tokens.pop(0)
            return Identifier(token.loc, token.src)
        if isinstance(tokens[0], t1.Symbol) and tokens[0].src in symbolic_identifiers:
            token = tokens.pop(0)
            return Identifier(token.loc, token.src)
        return None

class Operator(Token2):
    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'Operator|None':
        raise NotImplementedError()

class Keyword(Token2): # e.g. if, loop, import, let, etc. any keyword that behaves differently syntactically e.g. `<keyword> <expr>`. Ignore keywords that can go in identifiers, e.g. `void`, `intrinsic`/`extern`, etc.
    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'Keyword|None':
        if isinstance(tokens[0], t1.Identifier) and tokens[0].src in keywords:
            token = tokens.pop(0)
            return Keyword(token.loc, token.src)
        return None

class Hashtag(Token2):
    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'Hashtag|None':
        raise NotImplementedError()

class Integer(Token2):
    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'Integer|None':
        raise NotImplementedError()

class Whitespace(Token2): # so we can invert later for juxtapose
    @staticmethod
    def eat(tokens:list[t1.Token]) -> 'Whitespace|None':
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

def tokenize2(tokens:list[t1.Token]) -> list[Token2]:
    processed: list[Token2] = []
    while len(tokens) > 0:
        for token_cls in top_level_tokens:
            if (token := token_cls.eat(tokens)) is not None:    
                processed.append(token)
                break
        else:
            # TODO: proper error reporting
            raise ValueError(f"no token found for {tokens[0]}")
            
    return processed


def test():
    from ..myargparse import ArgumentParser
    from .tokenizer import tokens_to_report
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    tokens = t1.tokenize(srcfile)
    tokens2 = tokenize2(tokens)
    print(tokens_to_report(tokens2, srcfile))


if __name__ == '__main__':
    test()