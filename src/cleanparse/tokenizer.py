from .errors import Span, Error, SrcFile, Pointer
from .utils import truncate
# from .meta import Tokenized, AST
from typing import TypeAlias
from dataclasses import dataclass
from abc import ABC, abstractmethod

import pdb

class Context(ABC):
    @abstractmethod
    def close(self, src:str) -> 'tuple[int, type[Token]] | None': ...

class Root(Context):
    def close(self, src:str) -> 'tuple[int, type[Token]] | None':
        return None

@dataclass
class StringBody(Context):
    delimiter: str
    def close(self, src:str) -> 'tuple[int, type[Token]] | None':
        if not src.startswith(self.delimiter):
            return None
        return len(self.delimiter), StringQuote

@dataclass
class BlockBody(Context):
    delimiter: str
    def close(self, src:str) -> 'tuple[int, type[Token]] | None':
        raise NotImplementedError("TODO: close based on matching delimiters")
 
# Context:TypeAlias = Root | StringBody # | BlockBody



@dataclass
class Token(ABC):
    src: str
    loc: Span

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.src}>"
    
    @staticmethod
    @abstractmethod
    def eat(src:str, ctx:Context) -> int|None:
        """Try to eat a token, return the number of characters eaten or None"""



# TODO: expand the list of valid identifier characters
digits = set('0123456789')
alpha = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
greek = set('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρςστυφχψω')
misc = set('_?!$&°')
start_characters = (alpha | greek | misc)
continue_characters = (alpha | digits | greek | misc)


class Identifier(Token):
    @staticmethod
    def eat(src:str, ctx:Context) -> int|None:
        """
        Identifiers:
        - may not start with a number
        - may not be an operator (handled by longest match + token precedence)
        """
        if src[0] not in start_characters:
            return None

        i = 1
        while i < len(src) and src[i] in continue_characters:
            i += 1

        return i

class Hashtag(Token):
    @staticmethod
    def eat(src: str, ctx:Context) -> int | None:
        """hashtags are just special identifiers that start with #"""
        if src.startswith('#'):
            i, _ = Identifier.eat(src[1:])
            if i is not None:
                return i + 1

        return None

class StringQuote(Token):
    @staticmethod
    def eat(src:str, ctx:Context) -> int|None:
        """string quotes are any odd-length sequence of either all single or all double quotes"""

        if src[0] not in '\'"':
            return None
        i = 1
        quote_continuation = src[0] * 2
        while src[i:].startswith(quote_continuation):
            i += 2
        return i

class StringChars(Token):
    @staticmethod
    def eat(src:str, ctx:Context) -> int|None:
        """regular characters are anything except for the delimiter, an escape sequence, or a block opening"""
        if not isinstance(ctx, StringBody):
            raise ValueError("INTERNAL ERROR: attempted to eat StringChars in a non-string context")
        i = 0
        while i < len(src) and not src[i:].startswith(ctx.delimiter) and src[i] not in '\\{':
            i += 1
        
        return i or None

# class StringEscape(Token): ...
# class BlockOpen(Token): ...
# class BlockClose(Token): ...
# class WhiteSpace(Token): ...



# Map from context to tokens that can appear in that context
context_map: dict[type[Context], list[type[Token]]] = {
    Root: [Identifier, StringQuote],
    StringBody: [StringChars], #, StringEscape, BlockOpen],
    # BlockBody: [BlockClose], #TODO: include the rest from Root
}

def tokenize(srcfile: SrcFile) -> list[Token]:
    ctx_stack: list[Context] = [Root()]
    tokens: list[Token] = []
    src = srcfile.body

    i = 0
    while i < len(src):
        # try to eat all allowed tokens at the current position
        ctx = ctx_stack[-1]
        allowed_tokens = context_map[type(ctx)]
        matches = [(token_cls.eat(src[i:], ctx), token_cls) for token_cls in allowed_tokens]                

        # filter out matches that didn't eat anything
        matches = [(length, token_cls) for length, token_cls in matches if length is not None]

        # filter matches shorter than the longest match
        matches = sorted(matches, key=lambda x: x[0], reverse=True)
        longest_match_length = matches[0][0] if len(matches) > 0 else 0
        matches = [match for match in matches if match[0] == longest_match_length]

        # if there are multiple matches, TODO: resolve with precedence
        if len(matches) > 1:
            error = Error(
                srcfile=srcfile,
                title=f"multiple tokens matched. Context={ctx.__class__.__name__}",
                pointer_messages=Pointer(span=Span(i, i+longest_match_length), message=f"multiple tokens matched at {i}..{i+longest_match_length}: {matches=}"),
                hint="TODO: tokenizer implementation is not yet implemented for multiple token matches"
            )
            error.throw()
        
        if len(matches) == 0:
            error = Error(
                srcfile=srcfile,
                title=f"no token matched. Context={ctx.__class__.__name__}",
                pointer_messages=Pointer(span=Span(i, i), message=f"no token matched at position {i}: {truncate(src[i:])}"),
            )
            error.throw()

        # add the token to the list of tokens
        length, token_cls = matches[0]
        token = token_cls(src[i:i+length], Span(i, i+length))
        tokens.append(token)
        i += length

    pdb.set_trace()
    
    return tokens


def test():
    from ..myargparse import ArgumentParser
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    tokens = tokenize(srcfile)
    print(tokens)

if __name__ == '__main__':
    test()