from .reporting import Span, Info, Error, SrcFile, Pointer
from .utils import truncate, descendants, ordinalize, first_line
from typing import TypeAlias, ClassVar, get_origin, get_args, Union, Protocol, Literal
from types import UnionType
from dataclasses import dataclass
from abc import ABC, abstractmethod
from functools import cache

import pdb

##### CONTEXT CLASSES #####

@dataclass
class Context(ABC):
    srcfile: SrcFile

class Root(Context): ...

@dataclass
class StringBody(Context):
    opening_quote: 'StringQuoteOpener|RestOfFileStringQuote|HeredocStringOpener'

@dataclass
class RawStringBody(Context):
    opening_quote: 'RawStringQuoteOpener|RawHeredocStringOpener'

@dataclass
class BlockBody(Context):
    opening_delim: 'LeftSquareBracket|LeftParenthesis|LeftCurlyBrace'
 
@dataclass
class TypeBody(Context):
    opening_delim: 'LeftAngleBracket'


##### Context Actions #####

@dataclass
class Push:
    ctx: Context
class Pop: ...

ContextAction: TypeAlias = Push | Pop | None


whitespace = {' ', '\t', '\n', '\r'} # TBD if we need \f and \v

# TODO: expand the list of valid identifier characters
digits = set('0123456789')
alpha = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
greek = set('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρςστυφχψω')
misc = set('_?!$°')
# see https://symbl.cc/en/collections/superscript-and-subscript-letters/ for more sub/superscript characters
subscripts   = set('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₔₕₖₗₘₙₚₛₜ')
superscripts = set('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᴬᴮᴰᴱᴲᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᵝᵞᵟᵠᵡᵐᵊᶿᵡꜝʱʴʵʶˠ')
primes = set('′″‴⁗') # suggested to actually only have the single prime, and allow it anywhere just like other decorations


start_characters = (alpha | greek | misc)
continue_characters = (alpha | digits | greek | misc)
decoration_characters = (superscripts | subscripts)

# note that the prefix is case insensitive, so call .lower() when matching the prefix
# numbers may have _ as a separator (if _ is not in the set of digits)
BasePrefix: TypeAlias = Literal['0b', '0t', '0q', '0s', '0o', '0d', '0z', '0x', '0u', '0r', '0g']
number_bases: dict[BasePrefix, set[str]] = {
    '0b': {*'01'},  # binary
    '0t': {*'012'},  # ternary
    '0q': {*'0123'},  # quaternary
    '0s': {*'012345'},  # seximal
    '0o': {*'01234567'},  # octal
    '0d': {*'0123456789'},  # decimal
    '0z': {*'0123456789xeXE'},  # dozenal (case-insensitive)
    '0x': {*'0123456789abcdefABCDEF'},  # hexadecimal (case-insensitive)
    '0u': {*'0123456789abcdefghijklmnopqrstuvABCDEFGHIJKLMNOPQRSTUV'},  # base 32 (duotrigesimal)
    '0r': {*'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'},  # base 36 (hexatrigesimal)
    '0g': {*'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!$'},  # base 64 (tetrasexagesimal)
}

@cache
def is_based_digit(digit: str, base: str) -> bool:
    """determine if a digit is valid in a given base"""
    digits = number_bases[base]
    return digit in digits



# TODO: consider if \ is useful as a symbol (or combined with other stuff) in non-string contexts
symbolic_operators = sorted([
    '~', '@', '`',
    '?', ';',
    '+', '-', '*', '/', '//', '^',
    '=?', '>?', '<?', '>=?', '<=?', 'in?', 'is?', 'isnt?', '<=>',
    '|', '&', '??',
    '=', '::', ':=' # not a walrus operator. `x:=y` is sugar for `let x=y` (TODO: move this description to where ever we describe all operators, e.g. docs)
    '@?',
    '|>', '<|', '=>',
    '->', '<->',
    '.', '..', '...', ',', ':', ':>',
], key=len, reverse=True)

# shift operators are not allowed in type groups, so deal with them separately
shift_operators = sorted(['<<', '>>', '<<<', '>>>', '<<!', '!>>'], key=len, reverse=True)


# legal characters for use in heredoc delimiters: any identifier character or symbol character except for quotes `"`, `'`
legal_heredoc_delim_chars = (
    start_characters |
    continue_characters |
    decoration_characters |
    digits |
    primes |
    set(''.join(symbolic_operators + shift_operators + ['\\#%()[]{} '])) #include \, #, %, (), [], {}, and ` ` (<space>) manually since currently not in any symbol or identifier characters
)


@dataclass
class Token[T:Context](ABC):
    src: str
    loc: Span
    valid_contexts: ClassVar[set[type[Context]]] = None # must be defined by subclass type parameters

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.src}>"

    @staticmethod
    @abstractmethod
    def eat(src:str, ctx:T) -> int|None:
        """Try to eat a token, return the number of characters eaten or None"""

    def action_on_eat(self, ctx:T) -> ContextAction:
        """
        Called when the token is eaten.
        Return a new context to push onto the context stack or pop the current from the stack.
        Return None to keep the current context.
        """
        return None

    def __init_subclass__(cls: type['Token'], **kwargs):
        """verify that subclasses parameterize Token with a context argument and set the valid_contexts class variable"""
        super().__init_subclass__(**kwargs)
        cls.valid_contexts = set(cls._get_ctx_params())

    @classmethod
    def _get_ctx_params(cls: type['Token']) -> list[type[Context]]:
        """get the type parameters of the child class (e.g. class Identifier(Token[GeneralBodyContexts])) -> [*GeneralBodyContexts]"""
        for base in getattr(cls, '__orig_bases__', []):
            if get_origin(base) is Token:
                args = get_args(base)
                if len(args) != 1:
                    raise ValueError(f"class {cls.__name__} must have exactly one type parameter argument. Got {len(args)} arguments: {args}")

                # if it's a union, pull out all the members, otherwise return the single parameter
                arg = args[0]
                if get_origin(arg) in (Union, UnionType):
                    params = list(get_args(arg))
                else:
                    params = [arg]
                assert all(issubclass(p, Context) for p in params), f"all context parameters in {cls.__name__}(Token[...]) must be subclasses of Context. Invalid parameters: {set(params) - {*descendants(Context)}}"
                return params
        raise ValueError(f"class {cls.__name__} does not parameterize Token with any contexts. Expected `class {cls.__name__}(Token[SomeContexts])`")



##### TOKEN CLASSES #####
GeneralBodyContexts: TypeAlias = Root | BlockBody | TypeBody
BodyWithoutTypeContexts: TypeAlias = Root | BlockBody
BodyOrStringContexts: TypeAlias = Root | BlockBody | TypeBody | StringBody
StringContexts: TypeAlias = StringBody | RawStringBody

class WhiteSpace(Token[GeneralBodyContexts]):
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """white space is any sequence of whitespace characters"""
        i = 0
        while i < len(src) and src[i] in whitespace:
            i += 1
        return i or None


class LineComment(Token[GeneralBodyContexts]):
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """line comments are any sequence of characters after a % until the end of the line"""
        if not src.startswith('%') or src.startswith('%{'):
            return None
        i = 1
        while i < len(src) and src[i] != '\n':
            i += 1
        if i < len(src): # include the newline in the comment (if we're not EOF)
            i += 1
        return i


class BlockComment(Token[GeneralBodyContexts]):
    @staticmethod
    def eat(src: str, ctx:GeneralBodyContexts) -> int | None:
        """
        Block comments are of the form %{ ... }% and can be nested.
        """
        if not src.startswith("%{"):
            return None

        openers: list[Span] = []
        i = 0

        while i < len(src):
            if src[i:].startswith('%{'):
                openers.append(Span(i, i + 2))
                i += 2
            elif src[i:].startswith('}%'):
                openers.pop()
                i += 2

                if len(openers) == 0:
                    return i
            else:
                i += 1

        # error, unterminated block comment(s)
        span_offset = ctx.srcfile.body.index(src)
        plural = 's' if len(openers) > 1 else ''
        error = Error(ctx.srcfile, title=f"{len(openers)} unterminated block comment{plural}", pointer_messages=[
            *(Pointer(Span(opener.start + span_offset, opener.stop + span_offset), message=f"{ordinalize(i+1)} unterminated block comment opened here{f' (inside {ordinalize(i)})' if i > 0 else ''}")
                for i, opener in enumerate(openers)
            ),
            Pointer(span=[
                *(
                    Span(o1.stop + span_offset, o2.start + span_offset)
                    for o1, o2 in zip(openers, openers[1:]) if o2.start >= o1.stop
                ),
                Span(openers[-1].stop + span_offset, len(src) + span_offset)
            ], message=f"Unbound block comment{plural}")
        ], hint=f"Did you forget {len(openers)} closing `}}%`?\nBlock comments start with `%{{` and end with `}}%` and can be nested")
        error.throw()



class Identifier(Token[GeneralBodyContexts]):
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """
        Identifiers:
        - may not start with a number
        - may not be an operator (handled by longest match + token precedence)
        - may contain decorator characters (superscripts/subscripts) anywhere (but must include at least one start character)
        """
        i = 0
        
        # Skip leading decorator characters
        while i < len(src) and src[i] in decoration_characters:
            i += 1
        
        # Must have at least one start character
        if i >= len(src) or src[i] not in start_characters:
            return None
        
        # Consume the start character
        i += 1
        
        # Continue consuming continue_characters or decorator characters
        while i < len(src) and (src[i] in continue_characters or src[i] in decoration_characters):
            i += 1
        
        # may optionally end with a prime
        if i < len(src) and src[i] in primes:
            i += 1
        
        return i


class Symbol(Token[GeneralBodyContexts]):
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """symbolic operators are any sequence of characters in the symbolic_operators set"""
        for op in symbolic_operators:
            if src.startswith(op):
                return len(op)
        return None


class ShiftSymbol(Token[BodyWithoutTypeContexts]):
    @staticmethod
    def eat(src:str, ctx:BodyWithoutTypeContexts) -> int|None:
        """shift operators are any sequence of characters in the shift_operators set"""
        for op in shift_operators:
            if src.startswith(op):
                return len(op)
        return None


class Hashtag(Token[GeneralBodyContexts]):
    @staticmethod
    def eat(src: str, ctx:GeneralBodyContexts) -> int | None:
        """hashtags are just special identifiers that start with #"""
        if src.startswith('#'):
            i = Identifier.eat(src[1:], ctx)
            if i is not None:
                return i + 1

        return None


# square brackets and parenthesis can mix and match for range syntax
class LeftSquareBracket(Token[GeneralBodyContexts]):
    matching_right: 'RightSquareBracket|RightParenthesis' = None
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        if src.startswith('['):
            return 1
        return None
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(BlockBody(ctx.srcfile, self))


class RightSquareBracket(Token[BlockBody]):
    matching_left: 'LeftSquareBracket|LeftParenthesis' = None
    
    @staticmethod
    def eat(src:str, ctx:BlockBody) -> int|None:
        if src.startswith(']'):
            return 1
        return None
    
    def action_on_eat(self, ctx:BlockBody):
        if isinstance(ctx.opening_delim, LeftCurlyBrace):
            error = Error(
                srcfile=ctx.srcfile,
                title=f"Mismatched opening and closing braces",
                pointer_messages=[
                    Pointer(span=ctx.opening_delim.loc, message=f"Opening brace"),
                    Pointer(span=self.loc, message=f"Mismatched closer. Expected `}}`"),
                ],
                hint=f"Did you forget a closing `}}`?"
            )
            error.throw()
        ctx.opening_delim.matching_right = self
        self.matching_left = ctx.opening_delim
        return Pop()


class LeftParenthesis(Token[GeneralBodyContexts]):
    matching_right: 'RightParenthesis|RightSquareBracket' = None
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        if src.startswith('('):
            return 1
        return None
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(BlockBody(ctx.srcfile, self))


class RightParenthesis(Token[BlockBody]):
    matching_left: 'LeftParenthesis|LeftSquareBracket' = None
    
    @staticmethod
    def eat(src:str, ctx:BlockBody) -> int|None:
        if src.startswith(')'):
            return 1
        return None
    
    def action_on_eat(self, ctx:BlockBody):
        if isinstance(ctx.opening_delim, LeftCurlyBrace):
            error = Error(
                srcfile=ctx.srcfile,
                title=f"Mismatched opening and closing braces",
                pointer_messages=[
                    Pointer(span=ctx.opening_delim.loc, message=f"Opening parenthesis"),
                    Pointer(span=self.loc, message=f"Mismatched closer. Expected `}}`"),
                ],
                hint=f"Did you forget a closing `}}`?"
            )
            error.throw()
        ctx.opening_delim.matching_right = self
        self.matching_left = ctx.opening_delim
        return Pop()


class LeftCurlyBrace(Token[BodyOrStringContexts]):
    matching_right: 'RightCurlyBrace' = None
    
    @staticmethod
    def eat(src:str, ctx:BodyOrStringContexts) -> int|None:
        if src.startswith('{'):
            return 1
        return None
    
    def action_on_eat(self, ctx:BodyOrStringContexts): return Push(BlockBody(ctx.srcfile, self))


class RightCurlyBrace(Token[BlockBody]):
    matching_left: 'LeftCurlyBrace' = None
    
    @staticmethod
    def eat(src:str, ctx:BlockBody) -> int|None:
        if src.startswith('}'):
            return 1
        return None
    
    def action_on_eat(self, ctx:BlockBody):
        if isinstance(ctx.opening_delim, (LeftSquareBracket, LeftParenthesis)):
            term = 'bracket' if isinstance(ctx.opening_delim, LeftSquareBracket) else 'parenthesis'
            error = Error(
                srcfile=ctx.srcfile,
                title=f"Mismatched opening and closing brackets/parentheses",
                pointer_messages=[
                    Pointer(span=ctx.opening_delim.loc, message=f"Opening {term}"),
                    Pointer(span=self.loc, message=f"Mismatched closer. Expected `]` or `)`"),
                ],
                hint=f"Did you forget a closing `)` or `]`?"
            )
            error.throw()
        ctx.opening_delim.matching_right = self
        self.matching_left = ctx.opening_delim
        return Pop()


class LeftAngleBracket(Token[GeneralBodyContexts]):
    matching_right: 'RightAngleBracket' = None
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        if src.startswith('<'):
            return 1
        return None
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(TypeBody(ctx.srcfile, self))


class RightAngleBracket(Token[TypeBody]):
    matching_left: 'LeftAngleBracket' = None
    
    @staticmethod
    def eat(src:str, ctx:TypeBody) -> int|None:
        if src.startswith('>'):
            return 1
        return None
    
    def action_on_eat(self, ctx:TypeBody):
        ctx.opening_delim.matching_right = self
        self.matching_left = ctx.opening_delim
        return Pop()


class StringQuoteOpener(Token[GeneralBodyContexts]):
    matching_quote: 'StringQuoteCloser' = None

    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """string quotes are any odd-length sequence of either all single or all double quotes"""
        # only match if the first character is a quote
        if src[0] not in '\'"':
            return None
        
        # # in a string body, the only kind of quote that can be matched is the matching closing quote
        # if isinstance(ctx, StringBody):
        #     if not isinstance(ctx.opening_quote, StringQuote): return None
        #     if not src.startswith(ctx.opening_quote.src): return None
        #     return len(ctx.opening_quote.src)
        
        # # in a raw string body, see if we match the opening quote (minus the r prefix)
        # if isinstance(ctx, RawStringBody):
        #     if not isinstance(ctx.opening_quote, RawStringQuote): return None
        #     if not src.startswith(ctx.opening_quote.src[1:]): return None
        #     return len(ctx.opening_quote.src[1:])


        # match opening quotes
        i = 1
        quote = src[0]
        while src[i:].startswith(quote):
            i += 1
        
        # if total is an even, this indicates empty string, so only eat the first half
        if i % 2 == 0:
            return i // 2
        
        # otherwise, eat the entire opening quote
        return i


        # # match 2 quotes at a time
        # i = 1
        # quote = src[0]
        # while src[i:].startswith(quote * 2):
        #     i += 2
        
        # # if total is an even, this indicates empty string
        # # eat just the opening quote
        # if src[i:].startswith(quote):
        #     return (i + 1) // 2

        # return i
    
    def action_on_eat(self, ctx:GeneralBodyContexts) -> ContextAction:
        # inside a string body, a quote closes the string
        # if isinstance(ctx, StringBody):
        #     assert isinstance(ctx.opening_quote, StringQuote), f"INTERNAL ERROR: unexpected closing quote type that matched an opening StringQuote: (closer){self=}, (opener){ctx.opening_quote=}"
        #     if ctx.opening_quote.src == self.src:
        #         self.matching_quote = ctx.opening_quote
        #         self.matching_quote.matching_quote = self
        #         return Pop()
        #     # unreachable
        #     raise ValueError(f"INTERNAL ERROR: attempted to eat non-matching StringQuote in a string body, but can only match the closing quote. {ctx.opening_quote.src=} {self.src=}")
        
        # # inside a raw string body, a quote closes the raw string
        # if isinstance(ctx, RawStringBody):
        #     assert isinstance(ctx.opening_quote, RawStringQuote), f"INTERNAL ERROR: unexpected closing quote type that matched an opening RawStringQuote: (closer){self=}, (opener){ctx.opening_quote=}"
        #     if ctx.opening_quote.src[1:] == self.src:
        #         self.matching_quote = ctx.opening_quote
        #         self.matching_quote.matching_quote = self
        #         return Pop()
        #     # unreachable
        #     raise ValueError(f"INTERNAL ERROR: attempted to eat RawStringQuote in a raw string body, but can only match the closing quote. {ctx.opening_quote.src[1:]=} {self.src=}")
        
        return Push(StringBody(ctx.srcfile, self))

class StringQuoteCloser(Token[StringContexts]):
    matching_quote: 'StringQuoteOpener|RawStringQuoteOpener' = None

    @staticmethod
    def eat(src:str, ctx:StringContexts) -> int|None:
        """a string quote closer is a matching opening quote"""
        if isinstance(ctx.opening_quote, StringQuoteOpener) and src.startswith(ctx.opening_quote.src):
            return len(ctx.opening_quote.src)
        if isinstance(ctx.opening_quote, RawStringQuoteOpener) and src.startswith(ctx.opening_quote.src[1:]):
            return len(ctx.opening_quote.src[1:])
        # Heredoc delimiters can't match here, and rest-of-file strings don't have a closing quote
        return None
    
    def action_on_eat(self, ctx:StringContexts):
        assert isinstance(ctx.opening_quote, (StringQuoteOpener, RawStringQuoteOpener)), f"INTERNAL ERROR: attempted to eat StringQuoteCloser for non-matching opening quote: {ctx.opening_quote=}"
        self.matching_quote = ctx.opening_quote
        self.matching_quote.matching_quote = self
        return Pop()

class StringChars(Token[StringBody]):
    @staticmethod
    def eat(src:str, ctx:StringBody) -> int|None:
        """regular characters are anything except for the delimiter, an escape sequence, or a block opening"""
        i = 0
        while (
            i < len(src)
            and not (isinstance(ctx.opening_quote, StringQuoteOpener) and src[i:].startswith(ctx.opening_quote.src))
            and not (isinstance(ctx.opening_quote, HeredocStringOpener) and src[i:].startswith(ctx.opening_quote.get_delim()))
            and src[i] not in r'\{'
        ):
            i += 1
        
        return i or None


class StringEscape(Token[StringBody]):
    @staticmethod
    def eat(src:str, ctx:StringBody) -> int|None:
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
        - (TODO) \u#### or \U#### for a unicode codepoints. Must be four hex digits [0-9a-fA-F]
        - (TODO) \u{##..##} or \U{##..##} for an arbitrary unicode character. Inside the braces defaults to hex, and users can get decimal by using the 0d prefix
        - (TODO) \x## or \X## for a raw byte value. Must be two hex digits [0-9a-fA-F]
        - (TODO) \x{##..##} or \X{##..##} for arbitrary byte sequences. Same idea as unicode--defaults to hex, and 0d prefix for decimal
        
        - catch all case: \ followed by any character not mentioned above. Converts to just the literal character itself without the backslash
          This is how to insert characters that have special meaning in the string, e.g.
          - \' converts to just a single quote '
          - \{ converts to just a single open brace {
          - \\ converts to just a single backslash \
          - \m converts to just a single character m
          - etc.
        """
        if not src.startswith('\\'):
            return None

        if len(src) == 1:
            # TODO: make this a full error report. incomplete escape + unterminated string + anything else on the stack
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


class RawStringQuoteOpener(Token[GeneralBodyContexts]):
    matching_quote: 'StringQuoteCloser' = None  # raw strings are closed by regular quotes
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """raw string quotes are r followed by any odd-length sequence of either all single or all double quotes"""
        if not src.startswith('r"') and not src.startswith("r'"):
            return None
        i = StringQuoteOpener.eat(src[1:], ctx)  # eat the quote without the r prefix
        assert i is not None, f"INTERNAL ERROR: failed to get quote part of raw string opener when already verified its presence. {ctx=}, {src=}"
        return i + 1
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(RawStringBody(ctx.srcfile, self))


class RawStringChars(Token[RawStringBody]):
    @staticmethod
    def eat(src:str, ctx:RawStringBody) -> int|None:
        """regular characters are anything except for the delimiter"""
        i = 0
        while (
            i < len(src)
            and not (isinstance(ctx.opening_quote, RawStringQuoteOpener) and src[i:].startswith(ctx.opening_quote.src[1:]))  # matches just the quote part of the opener without the `r` prefix
            and not (isinstance(ctx.opening_quote, RawHeredocStringOpener) and src[i:].startswith(ctx.opening_quote.get_delim()))
        ):
            i += 1
        
        return i or None

class RestOfFileStringQuote(Token[Root]):
    @staticmethod
    def eat(src:str, ctx:Root) -> int|None:
        """a string that has an opening delimiter but no closing delimiter (consumes until EOF)
        Opening delimiters #\""" #'''
        """
        if not src.startswith('#"""') and not src.startswith("#'''"):
            return None
        return 4
    
    def action_on_eat(self, ctx:Root): return Push(StringBody(ctx.srcfile, self))

class RawRestOfFileString(Token[Root]):
    @staticmethod
    def eat(src:str, ctx:Root) -> int|None:
        """a raw string that has an opening delimiter but no closing delimiter (consumes until EOF)
        Opening delimiters #r\""" #r'''
        """
        if not src.startswith('#r"""') and not src.startswith("#r'''"):
            return None
        return len(src)


class HeredocStringOpener(Token[GeneralBodyContexts]):
    matching_quote: 'HeredocStringCloser' = None

    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """heredoc string opening and closing quotes are `#"<delim>"` and `<delim>` respectively
        <delim> is an arbitrary user-defined delimiter. May use any identifier or symbol characters in the language except for quotes `"`, `'`
        """
        if not src.startswith('#"') and not src.startswith("#'"):
            return None
        
        # consume the delimiter
        i = 2
        while i < len(src) and src[i] in legal_heredoc_delim_chars:
            i += 1
        if i == 2:
            return None # probably an end-of-file string quote #""" or #''', or reached EOF. probably don't emit error here

        # must have ended the delimiter with a matching quote
        quote = src[1]
        if not src[i:].startswith(quote):
            return None #TODO: emit error here. basically saw `#"<delim>EOF` without the closing quote `"`

        delim = src[2:i]

        # ensure the delimiter isn't all space, and also may not start or end with space
        if src[2:i].strip() == '':
            offset = ctx.srcfile.body.index(src)
            error = Error(
                srcfile=ctx.srcfile,
                title=f"Heredoc delimiter cannot be all space",
                pointer_messages=Pointer(span=Span(offset + 2, offset + 2 + len(delim)), message=f"Heredoc delimiter"),
                hint=f"Heredoc delimiters must contain at least one non-space character, and may not start or end with space"
            )
            error.throw()
        # ensure the delimiter doesn't start or end with space
        if delim.startswith(' ') or delim.endswith(' '):
            offset = ctx.srcfile.body.index(src)
            leading_space_length = len(delim) - len(delim.lstrip())
            trailing_space_length = len(delim) - len(delim.rstrip())
            pointer_messages=[
                Pointer(span=Span(offset + 2+leading_space_length, offset + 2 + len(delim) - trailing_space_length), message=f"delimiter")
            ]
            if leading_space_length: pointer_messages.append(Pointer(span=Span(offset + 2, offset+2+leading_space_length), message=f"Leading space"))
            if trailing_space_length: pointer_messages.append(Pointer(span=Span(offset + 2 + len(delim) - trailing_space_length, offset + 2 + len(delim)), message=f"Trailing space"))
            error = Error(
                srcfile=ctx.srcfile,
                title=f"Heredoc delimiter cannot start or end with space",
                pointer_messages=pointer_messages,
                hint=f"Heredoc delimiters may not start or end with space. Remove any leading or trailing space from the delimiter, e.g. #{quote}{delim.strip()}{quote}"
            )
            error.throw()

        return i + 1
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(StringBody(ctx.srcfile, self))

    def get_delim(self) -> str:
        """get the delimiter from the string quote"""
        return self.src[2:-1]
    
class HeredocStringCloser(Token[StringContexts]):
    matching_quote: 'HeredocStringOpener|RawHeredocStringOpener' = None

    @staticmethod
    def eat(src:str, ctx:StringContexts) -> int|None:
        """a heredoc string closer is a matching opening quote"""
        if not isinstance(ctx.opening_quote, (HeredocStringOpener, RawHeredocStringOpener)):
            return None
        delimiter = ctx.opening_quote.get_delim()
        if not src.startswith(delimiter):
            return None
        return len(delimiter)
    
    def action_on_eat(self, ctx:StringContexts): return Pop()

class RawHeredocStringOpener(Token[GeneralBodyContexts]):
    matching_quote: 'HeredocStringCloser' = None

    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """raw heredoc string opening and closing quotes are `#r"<delim>"` and `<delim>` respectively
        <delim> is an arbitrary user-defined delimiter. May use any identifier or symbol characters in the language except for quotes `"`, `'`
        """
        if not src.startswith('#r"') and not src.startswith("#r'"):
            return None
        i = HeredocStringOpener.eat('#'+src[2:], ctx)
        if i is None:
            return None
        return i + 1  # +1 for the `r` in the prefix
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(RawStringBody(ctx.srcfile, self))

    def get_delim(self) -> str:
        """get the delimiter from the string quote"""
        return self.src[3:-1]



class Number(Token[GeneralBodyContexts]):
    prefix: BasePrefix | None = None
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """a based number is a sequence of 1 or more digits, optionally preceded by a (case-insensitive) base prefix"""
        # try all known bases
        for base, digits in number_bases.items():
            # check if the src starts with the base prefix
            if src[:2].casefold().startswith(base):
                i = 2
                # Require at least one digit
                if not (i < len(src) and src[i] in digits):
                    return None
                # consume digits or underscores
                while i < len(src) and (src[i] in digits or src[i] == '_'):
                    i += 1
                return i
        
        # try decimal with no prefix
        i = 0
        digits = number_bases['0d']
        if not (i < len(src) and src[i] in digits):
            return None
        # consume digits or underscores
        while i < len(src) and (src[i] in digits or src[i] == '_'):
            i += 1
        
        return i or None
    
    def action_on_eat(self, ctx:GeneralBodyContexts):
        if self.src[:2].casefold() in number_bases:
            self.prefix = self.src[:2].casefold()

        #doesn't modify the context stack
        return None


##### Bespoke error cases #####

class KnownErrorCase(Protocol):
    def __call__(self, src: str, i: int, tokens: list[Token], ctx_stack: list[Context], ctx_history: list[Context]) -> Error|None: ...

def shift_operator_inside_type_param(src: str, i: int, tokens: list[Token], ctx_stack: list[Context], ctx_history: list[Context]) -> Error|None:
    if len(ctx_history) > 0 and isinstance(ctx_history[-1], TypeBody) and isinstance(tokens[-1], RightAngleBracket) and src[i:].startswith('>'):
        return Error(
            srcfile=ctx_stack[0].srcfile,
            title=f"Shift operator inside type parameter",
            pointer_messages=[
                Pointer(span=Span(i-1, i+1), message=f"Shift operator"),
                Pointer(span=Span(i, i), message=f"Tokenized as a type parameter closing delimiter"),
            ],
            hint=f"Shift operations may not be used directly within a type parameter.\nPerhaps you meant to wrap the expression in parentheses\ne.g. `something<(a >> b)>` instead of `something<a >> b>`"
        )


known_error_cases: list[KnownErrorCase] = [
    shift_operator_inside_type_param,
    # TODO: other known error cases
]


def collect_remaining_context_errors(ctx_stack: list[Context], max_pos:int|None=None) -> list[Error]:
    srcfile = ctx_stack[0].srcfile
    src = srcfile.body
    max_pos = len(src) if max_pos is None else min(max_pos, len(src))
    
    error_stack = []
    for ctx in reversed(ctx_stack):
        match ctx:
            case StringBody(opening_quote=o):
                error_stack.append(Error(srcfile, title=f"Missing string closing quote", pointer_messages=[
                    Pointer(span=o.loc, message=f"String opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message=f"String body"),
                    Pointer(span=Span(max_pos, max_pos), message=f"End without closing quote"),
                ], hint=f"Did you forget a `{o.src}`?"))
            case RawStringBody(opening_quote=o):
                error_stack.append(Error(srcfile, title=f"Missing raw string closing quote", pointer_messages=[
                    Pointer(span=o.loc, message=f"Raw string opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message=f"Raw string body"),
                    Pointer(span=Span(max_pos, max_pos), message=f"End without closing quote"),
                ], hint=f"Did you forget a `{o.src[1:]}`?"))
            case BlockBody(opening_delim=o):
                possible_closers = '`}`' if isinstance(o, LeftCurlyBrace) else '`]` or `)`'
                error_stack.append(Error(srcfile, title=f"Missing block closing delimiter", pointer_messages=[
                    Pointer(span=o.loc, message=f"Block opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message=f"Block body"),
                    Pointer(span=Span(max_pos, max_pos), message=f"End without closing delimiter"),
                ], hint=f"Did you forget a {possible_closers}?"))
            case TypeBody(opening_delim=o):
                error_stack.append(Error(srcfile, title=f"Missing type block closing chevron", pointer_messages=[
                    Pointer(span=o.loc, message=f"Type block opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message=f"Type block body"),
                    Pointer(span=Span(max_pos, max_pos), message=f"End without closing delimiter"),
                ], hint=f"Did you forget a `>`?"))
            case Root(): ... # root isn't an error (unless it somehow isn't the final context, but that should never happen)
            case _:
                raise NotImplementedError(f"INTERNAL ERROR: unhandled context: {ctx=}")
            # TODO: other cases
    
    return error_stack


##### TOKENIZER #####

def tokenize(srcfile: SrcFile) -> list[Token]:
    ctx_stack: list[Context] = [Root(srcfile)]
    ctx_history: list[Context] = []
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
            # check for known error cases
            for known_err_case in known_error_cases:
                error = known_err_case(src, i, tokens, ctx_stack, ctx_history)
                if error:
                    error.throw()
            # TODO: probably a better way to handle would be for checking if any upper contexts support the next token
            # potentially could use as a trick to recover/resynchronize and parse more tokens
            # TBD: what about the other way around, e.g. if the user didn't open a context they are trying to close?
            # could check what contexts support the next token--starts to get pretty heavy / complex
            error = Error(
                srcfile=srcfile,
                title=f"no valid token matched. Context={ctx.__class__.__name__}",
                pointer_messages=Pointer(span=Span(i, i), message=f"no token matched at position {i}: {truncate(first_line(src[i:]))}"),
            )
            print(error)

            error_stack = collect_remaining_context_errors(ctx_stack, max_pos=i)
            # for error in error_stack:
            if len(error_stack) > 0:
                print(error_stack[0])
            print("-"*80)
            print(tokens_to_report(tokens, srcfile))
            exit(1)

        # add the token to the list of tokens
        length, token_cls = matches[0]
        token = token_cls(src[i:i+length], Span(i, i+length))
        action = token.action_on_eat(ctx)
        if action is not None:
            if isinstance(action, Push):
                ctx_stack.append(action.ctx)
            elif isinstance(action, Pop):
                ctx_history.append(ctx_stack.pop())
            else:
                raise ValueError(f"INTERNAL ERROR: invalid context action: {action=}. Expected Push or Pop")
        tokens.append(token)
        i += length
    
    # pop any remaining rest-of-file string if present
    if len(ctx_stack) == 2 and isinstance(ctx_stack[-1], StringBody) and isinstance(ctx_stack[-1].opening_quote, RestOfFileStringQuote):
        ctx_stack.pop()

    # ensure that the final context is a root 
    if not isinstance(ctx_stack[-1], Root):
        error_stack = collect_remaining_context_errors(ctx_stack)
        for error in error_stack:
            print(error)
        exit(1)
    
    
    return tokens

def tokens_to_report(tokens: list[Token], srcfile: SrcFile) -> Info:
    return Info(
        srcfile=srcfile,
        title="Tokens consumed so far",
        pointer_messages=[Pointer(span=token.loc, message=f"{token.__class__.__name__}", color_id=hash(token.__class__)) for token in tokens],
    )

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

    # to print out report of all tokens eaten    
    print(tokens_to_report(tokens, srcfile))

if __name__ == '__main__':
    test()