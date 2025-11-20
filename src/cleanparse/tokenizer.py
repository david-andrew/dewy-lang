from .errors import Span, Info, Error, SrcFile, Pointer
from .utils import truncate, descendants
from typing import TypeAlias, ClassVar
from dataclasses import dataclass
from abc import ABC, abstractmethod

import pdb

##### CONTEXT CLASSES #####

class Context(ABC): ...

class Root(Context): ...

@dataclass
class StringBody(Context):
    opening_quote: 'StringQuote'

class RawStringBody(StringBody): ...

@dataclass
class BlockBody(Context):
    openening_delim: 'SquareBracket|Parenthesis|CurlyBrace'
 
@dataclass
class TypeBody(Context):
    openening_delim: 'AngleBracket'


##### Context Actions #####

@dataclass
class Push:
    ctx: Context
class Pop: ...

ContextAction: TypeAlias = Push | Pop | None

"""
(potentially moot given how tokens handle context updates)
Example case that is tricky with context.close

sometype< x>?10 >

`>?` is an operator, but if context closers always take precedence, then we'd get the `>` closing the type param block

But a reverse case where we want higher precedence is:

'this is a string'''
the rule is the first quote at the end closes the string, and then the next two are recognized as an empty string
<quote1>this is a string<quote1><juxtapose><quote1><quote1>
<quote1>this is a string<quote3>
I.e. when we're matching tokens, it'd be possible to see a triple quote token, which would beat the single quote on longest match,
but the single quote should still take precedence since it closes the context
---> one possible way around would be if somehow we could prevent longer quotes in the given context

[solved string issue by having string token behave differently in StringBody]
"""


# TODO: expand the list of valid identifier characters
digits = set('0123456789')
alpha = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
greek = set('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρςστυφχψω')
misc = set('_?!$&°')
start_characters = (alpha | greek | misc)
continue_characters = (alpha | digits | greek | misc)

# note that the prefix is case insensitive, so call .lower() when matching the prefix
# numbers may have _ as a separator (if _ is not in the set of digits)
number_bases = {
    '0b': {*'01'},  # binary
    '0t': {*'012'},  # ternary
    '0q': {*'0123'},  # quaternary
    '0s': {*'012345'},  # seximal
    '0o': {*'01234567'},  # octal
    '0d': {*'0123456789'},  # decimal
    '0z': {*'0123456789xeXE'},  # dozenal
    '0x': {*'0123456789abcdefABCDEF'},  # hexadecimal
    '0u': {*'0123456789abcdefghijklmnopqrstuvABCDEFGHIJKLMNOPQRSTUV'},  # base 32 (duotrigesimal)
    '0r': {*'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'},  # base 36 (hexatrigesimal)
    '0y': {*'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!$'},  # base 64 (tetrasexagesimal)
}

def is_based_digit(digit: str, base: str) -> bool:
    """determine if a digit is valid in a given base"""
    digits = number_bases[base]
    return digit in digits



@dataclass
class Token(ABC):
    src: str
    loc: Span
    valid_contexts: ClassVar[set[type[Context]]] = None # must be defined by subclass

    def __init_subclass__(cls: type['Token'], **kwargs):
        """verify that subclass has defined valid_contexts"""
        if not hasattr(cls, 'valid_contexts') or cls.valid_contexts is None:
            raise TypeError(f"subclass {cls.__name__} must define class level `valid_contexts = {{...}}`")
        assert all(issubclass(ctx, Context) for ctx in cls.valid_contexts), f"all contexts in valid_contexts must be subclasses of Context. Invalid contexts: {cls.valid_contexts - {*descendants(Context)}}"
        super().__init_subclass__(**kwargs)
        
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.src}>"
    
    @staticmethod
    @abstractmethod
    def eat(src:str, ctx:Context) -> int|None:
        """Try to eat a token, return the number of characters eaten or None"""
    
    def action_on_eat(self, ctx:Context) -> ContextAction:
        """
        Called when the token is eaten.
        Return a new context to push onto the context stack or pop the current from the stack.
        Return None to keep the current context.
        """
        return None


class Identifier(Token):
    valid_contexts = {Root, BlockBody, TypeBody}

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
    valid_contexts = {Root, BlockBody, TypeBody}

    @staticmethod
    def eat(src: str, ctx:Context) -> int | None:
        """hashtags are just special identifiers that start with #"""
        if src.startswith('#'):
            i, _ = Identifier.eat(src[1:])
            if i is not None:
                return i + 1

        return None

class StringQuote(Token):
    valid_contexts = {Root, BlockBody, TypeBody, StringBody}
    matching_quote: 'StringQuote' = None

    @staticmethod
    def eat(src:str, ctx:Context) -> int|None:
        """string quotes are any odd-length sequence of either all single or all double quotes"""
        # only match if the first character is a quote
        if src[0] not in '\'"':
            return None
        
        # in a string body, the only kind of quote that can be matched is the matching closing quote
        if isinstance(ctx, StringBody):
            if not src.startswith(ctx.opening_quote.src):
                return None
            return len(ctx.opening_quote.src)

        # inside a string body, we may only match up to the delimiter length        
        max_length = len(ctx.opening_quote.src) if isinstance(ctx, StringBody) else float('inf')

        # match 2 quotes at a time
        i = 1
        quote = src[0]
        while i < max_length and src[i:].startswith(quote * 2):
            i += 2
        
        # if total is an even, this indicates empty string
        # eat just the opening quote
        if src[i:].startswith(quote):
            return (i + 1) // 2

        return i
    
    def action_on_eat(self, ctx:Context) -> ContextAction:
        if isinstance(ctx, StringBody):
            if ctx.opening_quote.src == self.src:
                self.matching_quote = ctx.opening_quote
                self.matching_quote.matching_quote = self
                return Pop()
            raise ValueError(f"INTERNAL ERROR: attempted to eat StringQuote in a string body, but can only match the closing quote. {ctx.opening_quote.src=} {self.src=}")
        return Push(StringBody(self))


# TODO: perhaps have a block delim class that these inherit from
class SquareBracket(Token):
    valid_contexts = {Root, BlockBody, TypeBody}
class Parenthesis(Token):
    valid_contexts = {Root, BlockBody, TypeBody}
class CurlyBrace(Token):
    valid_contexts = {Root, BlockBody, TypeBody}
class AngleBracket(Token):
    valid_contexts = {Root, BlockBody, TypeBody}

class StringChars(Token):
    valid_contexts = {StringBody}

    @staticmethod
    def eat(src:str, ctx:Context) -> int|None:
        """regular characters are anything except for the delimiter, an escape sequence, or a block opening"""
        if not isinstance(ctx, StringBody):
            raise ValueError("INTERNAL ERROR: attempted to eat StringChars in a non-string context")
        i = 0
        while i < len(src) and not src[i:].startswith(ctx.opening_quote.src) and src[i] not in r'\{':
            i += 1
        
        return i or None

class StringEscape(Token):
    valid_contexts = {StringBody}

    # TODO: Note there is a current gap in constructable strings with escapes.
    # e.g. my_str = 'something \u38762<something>'
    # any hex characters [0-9a-fA-F] cannot be in <something> because they are just consumed by the unicode codepoint
    # specifically \a \b \f \0 are all problems because since those are escaped, we can't escape to get the character itself
    # the possible solution is to introduce another escape character that puts nothing, and acts just as a delimiter
    # e.g. my_str = 'something \u38762\ <something>' // or 'something \u38762\d<something>' or etc.
    # `\ ` is interesting because space probably never needs to be literally delimited
    # 'something {'\u38762'}<something>' technically works
    # 'something \u{38762}<something>' is the common form a lot of other languages support. looks plausible for dewy.
    @staticmethod
    def eat(src:str, ctx:Context) -> int|None:
        r"""
        Eat an escape sequence, return the number of characters eaten
        Escape sequences must be either a known escape sequence:
        - \n newline
        - \r carriage return
        - \t tab
        - \b backspace
        - \f form feed
        - \v vertical tab
        - \a alert
        - \0 null
        - \u##..# or \U##..# for an arbitrary unicode character. May have any number of hex digits
        - (TODO) \x## for a raw byte value. Must be two hex digits [0-9a-fA-F]. (or perhaps an even number of hex digits?)
        - (TODO) `\ ` (slash-space) for delimiting the end of a unicode codepoint, so the following character isn't consumed by it

        or a \ followed by an unknown character. In this case, the escape converts to just the unknown character
        This is how to insert characters that are otherwise illegal inside a string, e.g.
        - \' converts to just a single quote '
        - \{ converts to just a single open brace {
        - \\ converts to just a single backslash \
        - \m converts to just a single character m
        - etc.
        """
        if not isinstance(ctx, StringBody):
            raise ValueError("INTERNAL ERROR: attempted to eat StringEscape in a non-string context")

        if not src.startswith('\\'):
            return None

        if len(src) == 1:
            raise ValueError("unterminated escape sequence")

        if src[1] in 'uU':
            i = 2
            while i < len(src) and is_based_digit(src[i], '0x'):
                i += 1
            if i == 2:
                raise ValueError("invalid unicode escape sequence")
            return i

        # if src[1] in 'nrtbfva0':
        #     return 2

        # all other escape sequences (known or unknown) are just a single character
        return 2


# class BlockOpen(Token): ...
# class BlockClose(Token): ...
# class WhiteSpace(Token): ...



def tokenize(srcfile: SrcFile) -> list[Token]:
    ctx_stack: list[Context] = [Root()]
    tokens: list[Token] = []
    src = srcfile.body

    i = 0
    while i < len(src):
        # try to eat all allowed tokens at the current position
        ctx = ctx_stack[-1]
        allowed_tokens = [t for t in descendants(Token) if type(ctx) in t.valid_contexts]
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
        action = token.action_on_eat(ctx)
        if action is not None:
            if isinstance(action, Push):
                ctx_stack.append(action.ctx)
            elif isinstance(action, Pop):
                ctx_stack.pop()
            else:
                raise ValueError(f"INTERNAL ERROR: invalid context action: {action=}. Expected Push or Pop")
        tokens.append(token)
        i += length
    
    # ensure that the final context is a root
    if not isinstance(ctx_stack[-1], Root):
        error_stack = []
        for ctx in ctx_stack:
            match ctx:
                case StringBody(opening_quote=o):
                    error_stack.append(Error(srcfile, title=f"Missing string closing quote", pointer_messages=[
                        Pointer(span=o.loc, message=f"String opened here"),
                        Pointer(span=Span(o.loc.start+1, len(src)), message=f"String body"),
                        Pointer(span=Span(len(src), len(src)), message=f"End of file without closing quote"),
                    ]))
                # TODO: other cases
        
        for error in error_stack:
            print(error)
        exit(1)
    
    
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
    # print(tokens)

    # to print out report of all tokens eaten
    report = Info(
        srcfile=srcfile,
        title="tokenizer test",
        pointer_messages=[Pointer(span=token.loc, message=token.__class__.__name__)
            for token in tokens
        ]
    )
    report.pointer_messages.append(Pointer(span=Span(6,6), message="<juxtapose>")) #DEBUG for hello world program
    print(report)

if __name__ == '__main__':
    test()