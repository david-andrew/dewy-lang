"""
Tokenizer framework

This module implements a small declarative framework for tokenizing Dewy source.

Each concrete token is a subclass of `Token[T]`, where `T` is one or more
`Context` types indicating where that token is valid (e.g. `Root`, `StringBody`, `BlockBody`, etc.).
`Token.__init_subclass__` introspects the type parameter and builds a `valid_contexts` set for each token class.

During `tokenize`, we never hard-code a list of token types.
Instead, we dynamically (with caching) determine which tokens are allowed in a given context:
- look up all subclasses of `Token` via `descendants(Token)`,
- filter them by whether the current context type appears in their `valid_contexts`,
- then call `eat(src[i:], ctx)` on each allowed token class remaining.

Any token whose `eat` method returns a non-`None` length is considered a match.
We keep only the longest matches, then resolve any remaining ambiguities via `token_precedence`.

Each token class can also return a `Push` or `Pop` action from `action_on_eat`,
which updates a stack of `Context` objects (for example when entering or
leaving a block or string). This context stack controls which tokens are
eligible to match at each position, and lets the tokenizer enforce context-
sensitive rules (e.g. different tokens allowed inside strings vs. at the top
level) in a purely declarative way.
"""

from .reporting import Span, Info, Warning, Error, SrcFile, Pointer, ReportException
from .utils import truncate, descendants, ordinalize, first_line
from typing import NoReturn, TypeAlias, ClassVar, get_origin, get_args, Union, Protocol, Literal
from types import UnionType
from dataclasses import dataclass
from abc import ABC, abstractmethod
from functools import cache


import pdb

##### CHARACTER SETS AND USEFUL CONSTANTS #####

whitespace = {' ', '\t', '\n', '\r'}
ascii_control_chars = set(chr(i) for i in range(0x20) if i not in whitespace) | {'\x7F'} # most ascii<0x20 are ignored for security reasons
line_comment_start: Literal['%'] = '%'
block_comment_start: Literal['%{'] = '%{'
block_comment_end: Literal['}%'] = '}%'

# TODO: The specific set of digits is open for debate. The following are proposed:
# latin = set('ÆØÞßæøþẞ')
# misc = set('‽¢£¥€§†‡※')
# units = set('℃℉℥ℨ')
# Also `ϕϖϗϰϱϴ`, perhaps just `ϕϴ` which would normalize to the greek versions
digits = set('0123456789')
alpha = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
greek = set('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεϵζηθικλμνξοπρςστυφχψω')
math = set('ℂℕℤℚℝℙℍ𝔼𝕊𝕋𝔽𝔾ℵℒ')
misc = set('_‾?!$°')
subscripts   = set('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜᵢᵣᵤᵥⱼᵦᵧᵨᵩᵪ')
superscripts = set('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᴬᴭᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴻᴼᴾᴿᵀᵁᵂᵃᵅᵆᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᵝᵞᵟᵠᵡᶿꜝ')
misc_decorations = set('℠™©®')
primes = set('′″‴⁗')

start_characters = alpha | greek | math | misc # | latin | units
continue_characters = start_characters | digits
decoration_characters = superscripts | subscripts | misc_decorations | primes

# note that the prefix is case insensitive, so call .casefold() when matching the prefix
# numbers may have _ as a separator (if _ is not in the set of digits)
BasePrefix: TypeAlias = Literal['0b', '0t', '0q', '0s', '0o', '0d', '0z', '0x', '0u', '0r', '0g']
base_prefixes: set[BasePrefix] = set(BasePrefix.__args__)
base_digits: dict[BasePrefix, set[str]] = {
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
    '0g': {*'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+-/_='},  # base 64 (tetrasexagesimal)
}
base_radixes: dict[BasePrefix, int] = {
    '0b': 2,
    '0t': 3,
    '0q': 4,
    '0s': 6,
    '0o': 8,
    '0d': 10,
    '0z': 12,
    '0x': 16,
    '0u': 32,
    '0r': 36,
    '0g': 64,
}

# commonly used bases
base10: BasePrefix = '0d'
base16: BasePrefix = '0x'
MAX_NUMBER_BASE = 16  # maximum base for integer literals. Rest must be based strings or based arrays

@cache
def is_based_digit(digit: str, base: BasePrefix) -> bool:
    """determine if a digit is valid in a given base"""
    digits = base_digits[base]
    return digit in digits



symbols = sorted([
    '~', '@', '`',
    '?', ';',
    '+', '-', '*', '/', '//', '^',
    '\\', # left divide e.g. given Ax=b, x=A\b, where A\B ≡ solve(A B) (note this is not the same as x=A⁻¹B) (TODO: move description to docs)
    '=?', '>?', '<?', '>=?', '<=?', 'in?', 'is?', 'isnt?', '<=>',
    '|', '&', '??',
    '=', '::', ':=' # not a walrus operator. `x:=y` is sugar for `let x=y` (TODO: move this description to where ever we describe all operators, e.g. docs)
    '@?',
    '|>', '<|', '=>',
    '->', '<->',
    '.', '..', '...', ',', ':', ':>',
    '∞', '∅'
    # ⁂ ‰ ‱
], key=len, reverse=True)

# shift operators are not allowed in type groups, so deal with them separately
shift_operators = sorted(['<<', '>>', '<<<', '>>>', '<<!', '!>>'], key=len, reverse=True)


# legal characters for use in heredoc delimiters: any identifier character or symbol character except for quotes `"`, `'`
legal_heredoc_delim_chars = (
    start_characters |
    continue_characters |
    decoration_characters |
    digits |
    set(''.join(symbols + shift_operators + ['#%()[]{} '])) #include #, %, (), [], {}, and ` ` (<space>) manually since currently not in any symbol or identifier characters
)


##### CONTEXT CLASSES #####
# i.e. current state the tokenizer is in + any relevant state for that context

@dataclass
class Context(ABC):
    srcfile: SrcFile
    tokens_so_far: 'list[Token]'

    def current_tokenization_position(self) -> int:
        """Return the current position in the source string that the tokenizer is at"""
        if len(self.tokens_so_far) == 0: return 0
        return self.tokens_so_far[-1].loc.stop

@dataclass
class Root(Context):
    default_base: BasePrefix = base10

@dataclass
class StringBody(Context):
    opening_quote: 'StringQuoteOpener|RestOfFileStringQuote|HeredocStringOpener'

@dataclass
class RawStringBody(Context):
    opening_quote: 'RawStringQuoteOpener|RawHeredocStringOpener|RawRestOfFileStringQuote'

@dataclass
class BasedStringBody(Context):
    opening_quote: 'BasedStringQuoteOpener'
    base: BasePrefix

@dataclass
class BlockBody(Context):
    opening_delim: 'LeftSquareBracket|LeftParenthesis|LeftCurlyBrace|ParametricStringEscape'
    default_base: BasePrefix = base10
 

@dataclass
class TypeBody(Context):
    opening_delim: 'LeftAngleBracket'
    default_base: BasePrefix = base10

# convenient unions for common context combinations
# TODO: consider making it each context defines what tokens are valid for it, rather than tokens select from valid contexts
GeneralBodyContexts: TypeAlias = Root | BlockBody | TypeBody
BodyWithoutTypeContexts: TypeAlias = Root | BlockBody
WhitespaceOrCommentContexts: TypeAlias = Root | BlockBody | TypeBody | BasedStringBody# | BasedBlockBody

##### CONTEXT ACTIONS #####
# actions that can be taken when a token is eaten
# - Push: push a new context onto the context stack
# - Pop: pop the current context from the context stack
# - None: keep the current context

@dataclass
class Push:
    ctx: Context
class Pop: ...

ContextAction: TypeAlias = Push | Pop | None

##### TOKEN CLASSES AND EATING LOGIC #####

@dataclass
class Token[T:Context](ABC):
    """
    Base class for all tokens.

    Each concrete token is a `Token[T]` where `T` is one or more `Context`
    types (e.g. `Root`, `StringBody`, `BlockBody`). Subclasses declare where
    they are valid by choosing appropriate type parameters; `__init_subclass__`
    inspects those parameters and populates `valid_contexts` for the class.
    
    Example:
        ```
        class MyToken(Token[StringBody]): ...
        ``` 
        will only be considered when the current context is `StringBody`, while
        ```
        class AnotherToken(Token[GeneralBodyContexts]): ...
        ``` 
        will be considered in any of `Root`, `BlockBody`, or `TypeBody` contexts.

    The main `tokenize` loop discovers token classes dynamically via
    `descendants(Token)` and caches, for each `Context` type, the list of token
    classes whose `valid_contexts` contains that context type. For each token
    class allowed in the current context, it calls its `eat(src[i:], ctx)` method;
    eat methods return an integer length
    to indicate a match (and how many characters it is) or `None` if no match. 
    The tokenizer uses the longest match strategy to break ties, and may further
    break ties using `token_precedence` if multiple longest matches have the same length.

    After a token is instantiated, its `action_on_eat` result (`Push`, `Pop`,
    or `None`) updates the context stack (if needed). This design lets token
    classes declare both where they are legal and how they affect nesting
    structure, without having to be manually registered in the tokenizer.
    """
    src: str
    loc: Span
    idx: int
    valid_contexts: ClassVar[set[type[Context]]] = None # must be defined by subclass type parameters

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.src}>"

    @staticmethod
    @abstractmethod
    def eat(src:str, ctx:T) -> int|None:
        """
        Try to match a token
        
        Args:
            src (str): the source string to match against, starting at the current position
            ctx (Context): the current context mode the tokenizer is in
        
        Returns: 
            int | None: The number of characters eaten if successful, or `None` if no match.
        """

    def action_on_eat(self, ctx:T) -> ContextAction:
        """
        If overridden, indicates actions to perform on the context stack when a token is eaten.

        Args:
            ctx (Context): the current context mode the tokenizer is in

        Returns:
            ContextAction: a `Push`, `Pop`, or `None` action to perform on the context stack.
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


##### TOKEN CLASSES: WHITESPACE AND COMMENTS #####
# Tokens that consume layout-only characters or comments. These are valid in
# general body contexts and usually don't affect the context stack.

# TODO: want a warning if there is a lone \r not followed by \n
class Whitespace(Token[WhitespaceOrCommentContexts]):
    @staticmethod
    def eat(src:str, ctx:WhitespaceOrCommentContexts) -> int|None:
        """white space is any sequence of whitespace characters"""
        i = 0
        while i < len(src) and src[i] in whitespace:
            if src[i] == '\r' and not src[i+1:].startswith('\n'):
                Whitespace.warning_lone_carriage_return(src, i, ctx)
            i += 1
        return i or None
    
    @staticmethod
    def warning_lone_carriage_return(src: str, i: int, ctx: WhitespaceOrCommentContexts):
        warning = Warning(
            srcfile=ctx.srcfile,
            title="Lone carriage return",
            pointer_messages=[Pointer(span=Span(i, i+1), message="\\r without \\n")],
            hint="\\r should always be followed by \\n in Dewy source code. Recommend either removing the \\r or adding newline (\\r\\n)"
        )
        print(warning)


class LineComment(Token[WhitespaceOrCommentContexts]):
    @staticmethod
    def eat(src:str, ctx:WhitespaceOrCommentContexts) -> int|None:
        """line comments are any sequence of characters after a % until the end of the line"""
        if not src.startswith(line_comment_start):
            return None
        if src.startswith(block_comment_start):
            return None # don't start a line comment if it is actually a block comment
        
        # consume until the end of the line
        i = 1
        while i < len(src) and src[i] != '\n':
            i += 1
        if i < len(src): # include the newline in the comment (if we're not EOF)
            i += 1
        return i


class BlockComment(Token[WhitespaceOrCommentContexts]):
    @staticmethod
    def eat(src: str, ctx:WhitespaceOrCommentContexts) -> int | None:
        """
        Block comments are of the form %{ ... }% and can be nested.
        """
        if not src.startswith(block_comment_start):
            return None

        openers: list[Span] = []
        i = 0

        while i < len(src):
            if src[i:].startswith(block_comment_start):
                openers.append(Span(i, i + len(block_comment_start)))
                i += 2
            elif src[i:].startswith(block_comment_end):
                openers.pop()
                i += 2

                if len(openers) == 0:
                    return i
            else:
                i += 1

        # error, unterminated block comment(s)
        span_offset = ctx.current_tokenization_position()
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


##### TOKEN CLASSES: IDENTIFIERS AND SYMBOLIC OPERATORS #####
# Identifier-like things: plain identifiers and variants such as hashtags.

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
        
        return i


class Symbol(Token[GeneralBodyContexts]):
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """symbolic operators are any sequence of characters in the symbolic_operators set"""
        for op in symbols:
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


##### TOKEN CLASSES: DELIMITERS AND BLOCK / TYPE STRUCTURE #####
# Bracket and brace tokens open and close `BlockBody` or `TypeBody` contexts.
# Their `action_on_eat` methods push or pop the appropriate Context and also
# record matching pairs to support better error messages on mismatches.

# NOTE: square brackets and parenthesis can mix and match for range syntax, e.g. `[1..10)`
class LeftSquareBracket(Token[GeneralBodyContexts]):
    matching_right: 'RightSquareBracket|RightParenthesis' = None
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        if src.startswith('['):
            return 1
        return None
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(BlockBody(ctx.srcfile, ctx.tokens_so_far, self))


class RightSquareBracket(Token[BlockBody]):
    matching_left: 'LeftSquareBracket|LeftParenthesis|BasedBlockOpener' = None
    
    @staticmethod
    def eat(src:str, ctx:BlockBody) -> int|None:
        if src.startswith(']'):
            return 1
        return None
    
    def action_on_eat(self, ctx:BlockBody):
        if isinstance(ctx.opening_delim, (LeftSquareBracket, LeftParenthesis, BasedBlockOpener)):
            ctx.opening_delim.matching_right = self
            self.matching_left = ctx.opening_delim
            return Pop()

        if isinstance(ctx.opening_delim, (LeftCurlyBrace, ParametricStringEscape)):
            error = Error(
                srcfile=ctx.srcfile,
                title="Mismatched opening and closing delimiters",
                pointer_messages=[
                    Pointer(span=ctx.opening_delim.loc, message="Opening delimiter"),
                    Pointer(span=self.loc, message=f"Mismatched closer. Expected `}}` not `{self.src}`"),
                ],
                hint="Did you forget a closing `}`?"
            )
            error.throw()

        # unreachable
        raise ValueError(f"INTERNAL ERROR: unhandled opening delimiter that was closed with a RightSquareBracket: {ctx.opening_delim=}")            


class LeftParenthesis(Token[GeneralBodyContexts]):
    matching_right: 'RightParenthesis|RightSquareBracket' = None
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        if src.startswith('('):
            return 1
        return None
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(BlockBody(ctx.srcfile, ctx.tokens_so_far, self))


class RightParenthesis(Token[BlockBody]):
    matching_left: 'LeftParenthesis|LeftSquareBracket' = None
    
    @staticmethod
    def eat(src:str, ctx:BlockBody) -> int|None:
        if src.startswith(')'):
            return 1
        return None
    
    def action_on_eat(self, ctx:BlockBody):
        if isinstance(ctx.opening_delim, (LeftSquareBracket, LeftParenthesis)):
            ctx.opening_delim.matching_right = self
            self.matching_left = ctx.opening_delim
            return Pop()
        
        if isinstance(ctx.opening_delim, (LeftCurlyBrace, ParametricStringEscape)):
            error = Error(
                srcfile=ctx.srcfile,
                title="Mismatched opening and closing delimiters",
                pointer_messages=[
                    Pointer(span=ctx.opening_delim.loc, message="Opening delimiter"),
                    Pointer(span=self.loc, message=f"Mismatched closer. Expected `}}` not `{self.src}`"),
                ],
                hint="Did you forget a closing `}`?"
            )
            error.throw()
        
        # unreachable
        raise ValueError(f"INTERNAL ERROR: unhandled opening delimiter that was closed with a RightParenthesis: {ctx.opening_delim=}")            


class LeftCurlyBrace(Token[Root|BlockBody|TypeBody|StringBody]):
    matching_right: 'RightCurlyBrace' = None
    
    @staticmethod
    def eat(src:str, ctx:Root|BlockBody|TypeBody|StringBody) -> int|None:
        if src.startswith('{'):
            return 1
        return None
    
    def action_on_eat(self, ctx:Root|BlockBody|TypeBody|StringBody): return Push(BlockBody(ctx.srcfile, ctx.tokens_so_far, self))


class RightCurlyBrace(Token[BlockBody]):
    matching_left: 'LeftCurlyBrace' = None
    
    @staticmethod
    def eat(src:str, ctx:BlockBody) -> int|None:
        if src.startswith('}'):
            return 1
        return None
    
    def action_on_eat(self, ctx:BlockBody):
        if isinstance(ctx.opening_delim, (LeftCurlyBrace, ParametricStringEscape)):
            ctx.opening_delim.matching_right = self
            self.matching_left = ctx.opening_delim
            return Pop()
        
        if isinstance(ctx.opening_delim, (LeftSquareBracket, LeftParenthesis)):
            error = Error(
                srcfile=ctx.srcfile,
                title="Mismatched opening and closing delimiters",
                pointer_messages=[
                    Pointer(span=ctx.opening_delim.loc, message="Opening delimiter"),
                    Pointer(span=self.loc, message="Mismatched closer. Expected `]` or `)`"),
                ],
                hint="Did you forget a closing `)` or `]`?"
            )
            error.throw()
        
        # unreachable
        raise ValueError(f"INTERNAL ERROR: unhandled opening delimiter that was closed with a RightCurlyBrace: {ctx.opening_delim=}")            


class LeftAngleBracket(Token[GeneralBodyContexts]):
    matching_right: 'RightAngleBracket' = None
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        if src.startswith('<'):
            return 1
        return None
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(TypeBody(ctx.srcfile, ctx.tokens_so_far, self))


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


class BasedBlockOpener(Token[GeneralBodyContexts]):
    matching_right: 'RightSquareBracket'
    base: BasePrefix

    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        if len(src) < 3:
            return None
        if src[:2].casefold() not in base_radixes:
            return None
        if not src[2] == '[':
            return None
        return 3
    
    def action_on_eat(self, ctx:GeneralBodyContexts):
        self.base = self.src[:2].casefold()
        return Push(BlockBody(ctx.srcfile, ctx.tokens_so_far, self, self.base))

##### TOKEN CLASSES: STRINGS AND STRING BODIES #####
# String openers / closers and the tokens that consume within-string content.
# These manage `StringBody` or `RawStringBody` contexts and handle normal
# strings, raw strings, heredocs, and "rest-of-file" strings.

class StringQuoteOpener(Token[GeneralBodyContexts]):
    matching_quote: 'StringQuoteCloser' = None

    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """string quotes are any odd-length sequence of either all single or all double quotes"""
        # only match if the first character is a quote
        if src[0] not in '\'"':
            return None
        
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

    def action_on_eat(self, ctx:GeneralBodyContexts) -> ContextAction: return Push(StringBody(ctx.srcfile, ctx.tokens_so_far, self))

class StringQuoteCloser(Token[StringBody|RawStringBody|BasedStringBody]):
    matching_quote: 'StringQuoteOpener|RawStringQuoteOpener|BasedStringQuoteOpener' = None

    @staticmethod
    def eat(src:str, ctx:StringBody|RawStringBody|BasedStringBody) -> int|None:
        """a string quote closer is a matching opening quote"""
        if isinstance(ctx.opening_quote, StringQuoteOpener) and src.startswith(ctx.opening_quote.src):
            return len(ctx.opening_quote.src)
        if isinstance(ctx.opening_quote, RawStringQuoteOpener) and src.startswith(ctx.opening_quote.src[1:]):
            return len(ctx.opening_quote.src[1:])
        if isinstance(ctx.opening_quote, BasedStringQuoteOpener) and src.startswith(ctx.opening_quote.src[2:]):
            return len(ctx.opening_quote.src[2:])
        # Heredoc delimiters can't match here, and rest-of-file strings don't have a closing quote
        return None
    
    def action_on_eat(self, ctx:StringBody|RawStringBody|BasedStringBody):
        assert isinstance(ctx.opening_quote, (StringQuoteOpener, RawStringQuoteOpener, BasedStringQuoteOpener)), f"INTERNAL ERROR: attempted to eat StringQuoteCloser for non-matching opening quote: {ctx.opening_quote=}"
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
        
        Predefined escape sequences:
        - \n newline
        - \\n (i.e. \<newline>) a special case that basically ignores the newline and continues the string. Useful for ignoring newlines in multiline strings.
        - \r carriage return
        - \t tab
        - \b backspace
        - \f form feed
        - \v vertical tab
        - \a alert
        - \0 null
        - \u#### or \U#### for a unicode codepoints. Must be four hex digits [0-9a-fA-F]

        Catch-all case:
        - \ followed by any character not mentioned above converts to just the literal character itself without the backslash
        This is how to insert characters that have special meaning in the string, e.g.
        - \' converts to just a single quote '
        - \{ converts to just a single open brace {
        - \\ converts to just a single backslash \
        - \m converts to just a single character m
        - \<space> converts to just a single <space> character
        - etc.
        """
        if not src.startswith('\\'):
            return None

        if len(src) == 1:
            StringEscape.error_incomplete_string_escape(src, ctx)
        
        prefix_len = 2

        # hex/unicode
        if src[1] in 'uU' and not src[2:3] == '{':
            expected_digits = 4
            actual_digits = 0
            while (
                actual_digits < expected_digits
                and prefix_len + actual_digits < len(src)
                and is_based_digit(src[2 + actual_digits], base16)
            ):
                actual_digits += 1
            if actual_digits < expected_digits:
                StringEscape.error_invalid_width_hex_escape(src, ctx, expected_digits, actual_digits)
            return prefix_len + actual_digits

        # all other escape sequences (known or catch all) are just a single escape code
        return 2
    
    @staticmethod
    def error_incomplete_string_escape(src: str, ctx: StringBody) -> NoReturn:
        """Helper for when a string escape is incomplete"""
        offset = ctx.current_tokenization_position()
        error = Error(
            srcfile=ctx.srcfile,
            title="Incomplete escape sequence at end of string",
            pointer_messages=Pointer(span=Span(offset, offset+1), message="incomplete escape sequence"),
            hint="Finish the escape sequence (e.g. `\\n`, `\\u1234`, etc.) or remove the trailing backslash.",
        )
        error.throw()


    @staticmethod
    def error_invalid_width_hex_escape(src: str, ctx: StringBody, expected_digits: int, actual_digits: int) -> NoReturn:
        """Helper for when a hex or unicode escape doesn't have enough digits"""
        offset = ctx.current_tokenization_position()
        
        # build up error message
        name = 'unicode'
        remaining_digits_expected = expected_digits - actual_digits
        found_plural = 's' if actual_digits > 1 else ''
        expected_plural = 's' if remaining_digits_expected > 1 else ''
        example_digits = 'ff83' # just a random example of hex digits
        prefix_len = 2
        example_code = src[:prefix_len+actual_digits] + example_digits[:expected_digits-actual_digits]
        
        error = Error(
            srcfile=ctx.srcfile,
            title=f"{name.capitalize()} escape sequence is too short",
            pointer_messages=[
                Pointer(span=Span(offset, offset+prefix_len), message=f"{name.capitalize()} escape opened here"),
                *([Pointer(span=Span(offset+prefix_len, offset+prefix_len+actual_digits), message=f"found {actual_digits} hex digit{found_plural}")] if actual_digits > 0 else []),
                Pointer(span=Span(offset+prefix_len+actual_digits, offset+prefix_len+expected_digits), message=f"Expected {remaining_digits_expected} more hex digit{expected_plural}", color='red'),
            ],
            hint=f"{name.capitalize()} escape sequence must be {expected_digits} hex digits long. E.g. `{example_code}`"
        )
        error.throw()


class ParametricStringEscape(Token[StringBody]):
    matching_right: 'RightCurlyBrace' = None
    @staticmethod
    def eat(src:str, ctx:StringBody) -> int|None:
        r"""
        \u{##..##} or \U{##..##} for an arbitrary unicode character. Inside the braces defaults to hex, and users can get decimal by using the 0d prefix
        
        The block can also be an arbitrary expression, so long as it evaluates to an integer
        """
        if not src[:3].lower() == '\\u{':
            return None
        return 3
    
    def action_on_eat(self, ctx:StringBody): return Push(BlockBody(ctx.srcfile, ctx.tokens_so_far, self, base16))

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
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(RawStringBody(ctx.srcfile, ctx.tokens_so_far, self))


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
    
    def action_on_eat(self, ctx:Root): return Push(StringBody(ctx.srcfile, ctx.tokens_so_far, self))

class RawRestOfFileStringQuote(Token[Root]):
    @staticmethod
    def eat(src:str, ctx:Root) -> int|None:
        """a raw string that has an opening delimiter but no closing delimiter (consumes until EOF)
        Opening delimiters #r\""" #r'''
        """
        if not src.startswith('#r"""') and not src.startswith("#r'''"):
            return None
        return 5
    
    def action_on_eat(self, ctx:Root): return Push(RawStringBody(ctx.srcfile, ctx.tokens_so_far, self))


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
            HeredocStringOpener.error_incomplete_heredoc_delimiter(src, ctx, i)

        # ensure delimiter doesn't start or end with space
        HeredocStringOpener.check_error_heredoc_delimiter_space(src, ctx, i)

        return i + 1
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(StringBody(ctx.srcfile, ctx.tokens_so_far, self))

    def get_delim(self) -> str:
        """get the delimiter from the string quote"""
        return self.src[2:-1]
    
    @staticmethod
    def error_incomplete_heredoc_delimiter(src: str, ctx: GeneralBodyContexts, i: int) -> NoReturn:
        """Helper for when a heredoc delimiter is incomplete"""
        offset = ctx.current_tokenization_position()
        quote = src[1]
        wrong_quote = '"' if quote == "'" else "'"
        wrong_quoted = src[i:].startswith(wrong_quote)
        delim = src[2:i]
        example = f"#{quote}{delim}{quote}"
        error = Error(
            srcfile=ctx.srcfile,
            title="Incomplete heredoc delimiter",
            pointer_messages=[
                Pointer(span=Span(offset, offset+1), message="heredoc start"),
                Pointer(span=Span(offset+1, offset+2), message="heredoc delimiter opening quote"),
                *([Pointer(span=Span(offset+2, offset+2+len(delim)), message="delimiter")] if len(delim) > 0 else []),
                Pointer(span=Span(offset+2+len(delim), offset+2+len(delim)+1), message=f"Expected closing quote {quote} for heredoc delimiter"),
            ],
            hint=f'Did you mean to use {quote} to close instead of {wrong_quote} e.g. {example} not {example[:-1] + wrong_quote}' if wrong_quoted else f"Finish the heredoc delimiter (e.g. {example})",
        )
        error.throw()
    
    
    @staticmethod
    def check_error_heredoc_delimiter_space(src: str, ctx: GeneralBodyContexts, i: int) -> NoReturn|None:
        """Helper to check if a heredoc delimiter starts or ends with space"""
        delim = src[2:i]
        quote = src[1]

        # ensure the delimiter isn't all space, and also may not start or end with space
        if src[2:i].strip() == '':
            offset = ctx.current_tokenization_position()
            error = Error(
                srcfile=ctx.srcfile,
                title="Heredoc delimiter cannot be all space",
                pointer_messages=Pointer(span=Span(offset + 2, offset + 2 + len(delim)), message="Heredoc delimiter"),
                hint="Heredoc delimiters must contain at least one non-space character, and may not start or end with space"
            )
            error.throw()
        # ensure the delimiter doesn't start or end with space
        if delim.startswith(' ') or delim.endswith(' '):
            offset = ctx.current_tokenization_position()
            leading_space_length = len(delim) - len(delim.lstrip())
            trailing_space_length = len(delim) - len(delim.rstrip())
            pointer_messages=[
                Pointer(span=Span(offset + 2+leading_space_length, offset + 2 + len(delim) - trailing_space_length), message="delimiter")
            ]
            if leading_space_length: pointer_messages.append(Pointer(span=Span(offset + 2, offset+2+leading_space_length), message="Leading space"))
            if trailing_space_length: pointer_messages.append(Pointer(span=Span(offset + 2 + len(delim) - trailing_space_length, offset + 2 + len(delim)), message="Trailing space"))
            error = Error(
                srcfile=ctx.srcfile,
                title="Heredoc delimiter cannot start or end with space",
                pointer_messages=pointer_messages,
                hint=f"Heredoc delimiters may not start or end with space. Remove any leading or trailing space from the delimiter, e.g. #{quote}{delim.strip()}{quote}"
            )
            error.throw()


class HeredocStringCloser(Token[StringBody|RawStringBody]):
    matching_quote: 'HeredocStringOpener|RawHeredocStringOpener' = None

    @staticmethod
    def eat(src:str, ctx:StringBody|RawStringBody) -> int|None:
        """a heredoc string closer is a matching opening quote"""
        if not isinstance(ctx.opening_quote, (HeredocStringOpener, RawHeredocStringOpener)):
            return None
        delimiter = ctx.opening_quote.get_delim()
        if not src.startswith(delimiter):
            return None
        return len(delimiter)
    
    def action_on_eat(self, ctx:StringBody|RawStringBody): 
        ctx.opening_quote.matching_quote = self
        self.matching_quote = ctx.opening_quote
        return Pop()


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
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(RawStringBody(ctx.srcfile, ctx.tokens_so_far, self))

    def get_delim(self) -> str:
        """get the delimiter from the string quote"""
        return self.src[3:-1]

class BasedStringQuoteOpener(Token[GeneralBodyContexts]):
    matching_quote: 'StringQuoteCloser'
    base: BasePrefix

    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        if len(src) < 3:
            return None
        if src[:2].casefold() not in base_radixes:
            return None
        # eat an opening quote
        i = StringQuoteOpener.eat(src[2:], ctx)  # eat the quote without the r prefix
        if i is None: return None
        return i + 2

    def action_on_eat(self, ctx:GeneralBodyContexts):
        self.base = self.src[:2].casefold()
        return Push(BasedStringBody(ctx.srcfile, ctx.tokens_so_far, self, self.base))

class BasedStringChars(Token[BasedStringBody]):
    @staticmethod
    def eat(src:str, ctx:BasedStringBody) -> int|None:
        # eat any digit in the base or whitespace or underscore
        i = 0
        digits = base_digits[ctx.base]
        while i < len(src) and (src[i] in digits or src[i] == '_'):
            i += 1
        return i or None

##### TOKEN CLASSES: NUMBERS #####
# Based integer literals. The base may be given explicitly via a prefix or
# implicitly via the current Context's `default_base` (e.g. inside certain
# blocks). We record the resolved base prefix on the token in `action_on_eat`.

class Number(Token[GeneralBodyContexts]):
    prefix: BasePrefix
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """a based number is a sequence of 1 or more digits, optionally preceded by a (case-insensitive) base prefix (up to base-16)"""
        
        # try a number with a base prefix
        if src[:2].casefold() in base_prefixes:
            base = src[:2].casefold()
            digits = base_digits[base]
            if base_radixes[base] > MAX_NUMBER_BASE and len(src) > 2 and src[2] in digits: # skip if not a based number literal (e.g. based string)
                Number.error_too_high_number_base(src, ctx, base)
            i = 2
            # Require at least one digit
            if not (i < len(src) and src[i] in digits):
                # TODO: have error here if not a based string literal or based array literal
                return None
            # consume digits or underscores
            while i < len(src) and (src[i] in digits or src[i] == '_'):
                i += 1
            return i
        
        # try number with no prefix
        base = ctx.default_base if isinstance(ctx, BlockBody) else base10
        digits = base_digits[base]
        i = 0
        if not (i < len(src) and src[i] in digits):
            return None
        # consume digits or underscores
        while i < len(src) and (src[i] in digits or src[i] == '_'):
            i += 1
        
        return i or None
    
    def action_on_eat(self, ctx:GeneralBodyContexts):
        if self.src[:2].casefold() in base_digits:
            self.prefix = self.src[:2].casefold()
        else:
            self.prefix = ctx.default_base

        #doesn't modify the context stack
        return None
    

    @staticmethod
    def error_too_high_number_base(src: str, ctx:GeneralBodyContexts, base:BasePrefix):
        radix = base_radixes[base]
        digits_len = BasedStringChars.eat(src[2:], BasedStringBody(ctx.srcfile, ctx.tokens_so_far, None, base))
        assert digits_len is not None, "INTERNAL ERROR: based string chars should have been eaten"
        digits_str = src[2:2+digits_len]
        error = Error(
            srcfile=ctx.srcfile,
            title="number base too high",
            pointer_messages=[
                Pointer(span=Span(ctx.current_tokenization_position(), ctx.current_tokenization_position()+len(base)), message=f"base-{radix} prefix"),
                *([Pointer(span=Span(ctx.current_tokenization_position()+2, ctx.current_tokenization_position()+2+digits_len), message="unquoted digits", color='red')] if digits_len is not None else [])
            ],
            hint=f"Numeric literals only support up to base-{MAX_NUMBER_BASE} (Got base-{radix})\nTo represent larger bases, use a based string e.g. {base}'{digits_str}'"
        )
        error.throw()

class ExponentMarker(Token[GeneralBodyContexts]):
    power: Number

    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """
        an exponent marker is a single character `eE` or `pP` with a number before and a number after
        This is specifically to disambiguate for floats where the exponent part is read as an identifier
        e.g. 1e10 looks like <number 1><identifier e10>
        """
        if len(ctx.tokens_so_far) == 0 or not isinstance(ctx.tokens_so_far[-1], Number):
            return None
        if len(src) < 2:
            return None
        if src[0] not in 'eEpP':
            return None
        # don't check for +/- because it's not part of what we're trying to disambiguate
        if (i:=Number.eat(src[1:], ctx)) is None:
            return None
        return i + 1
    def action_on_eat(self, ctx:GeneralBodyContexts):
        self.power = Number(self.src[1:], Span(self.loc.start+1, self.loc.stop), self.idx)
        self.power.action_on_eat(ctx)
        return None
        

##### TOKEN CLASS PRECEDENCE #####
# for now, just use a simple list of pairs specifying cases of A > B
# TBD if we want a more global list, or what, but this should be good for now
# CAUTION: ensure no cycles in precedence levels
token_precedence: list[tuple[type[Token], type[Token]]] = [
    (Symbol, Identifier),
    (Number, Identifier),
    (ExponentMarker, Identifier),
    # TODO: other cases...
]


##### TOKENIZER ERROR CASES #####
# Error-case helpers that recognize specific tokenizer situations (e.g. shift
# operators in type parameters, ambiguous number vs identifier) and build
# detailed error objects to report to the user.

class NoMatchErrorCase(Protocol):
    def __call__(self, src: str, i: int, tokens: list[Token], ctx_stack: list[Context], ctx_history: list[Context]) -> Error|None: ...

class MultipleMatchedErrorCase(Protocol):
    def __call__(self, src: str, i: int, tokens: list[Token], ctx_stack: list[Context], ctx_history: list[Context], matches: list[tuple[int, type[Token]]]) -> Error|None: ...

def shift_operator_inside_type_param(src: str, i: int, tokens: list[Token], ctx_stack: list[Context], ctx_history: list[Context]) -> Error|None:
    if len(ctx_history) > 0 and isinstance(ctx_history[-1], TypeBody) and isinstance(tokens[-1], RightAngleBracket) and src[i:].startswith('>'):
        return Error(
            srcfile=ctx_stack[0].srcfile,
            title="Shift operator inside type parameter",
            pointer_messages=[
                Pointer(span=Span(i-1, i+1), message="Shift operator"),
                Pointer(span=Span(i, i), message="Tokenized as a type parameter closing delimiter"),
            ],
            hint="Shift operations may not be used directly within a type parameter.\nPerhaps you meant to wrap the expression in parentheses\ne.g. `something<(a >> b)>` instead of `something<a >> b>`"
        )
def ambiguous_number_or_identifier_in_parametric_string_escape(src: str, i: int, tokens: list[Token], ctx_stack: list[Context], ctx_history: list[Context], matches: list[tuple[int, type[Token]]]) -> Error|None:
    ctx = ctx_stack[-1]
    match_types = {match_type for _, match_type in matches}
    
    if (
        isinstance(ctx, BlockBody)
        and base_radixes[ctx.default_base] > 10 # anything with more than 10 digits could use letters as digits
        and len(matches) == 2
        and match_types == {Number, Identifier}
    ):
        match_len = matches[0][0]
        match_span = Span(i, i+match_len)
        radix = base_radixes[ctx.default_base]
        sequence = src[i:i+match_len]
        
        return Error(
            srcfile=ctx.srcfile,
            title="Ambiguous number or identifier in block body",
            pointer_messages=[
                Pointer(span=match_span, message=f"could be a base-{radix} number or an identifier"),
            ],
            hint=f"The current block is in base-{radix} mode.\nThe sequence `{sequence}` is both valid as a base-{radix} number and as an identifier.\nTo indicate a number:\n- add a leading `0` e.g. `0{sequence}`\n- add a base prefix e.g. `{ctx.default_base}{sequence}`\nTo indicate an identifier:\n- wrap in parentheses, e.g. `({sequence})`"
        )

def illegal_control_chars(src: str, i: int, tokens: list[Token], ctx_stack: list[Context], ctx_history: list[Context]) -> Error|None:
    j = i
    while j < len(src) and src[j] in ascii_control_chars:
        j += 1
    if j == i:
        return None
    
    plural = "s" if j - i > 1 else ""
    
    return Error(
            srcfile=ctx_stack[0].srcfile,
            title="Illegal control character",
            pointer_messages=Pointer(span=Span(i, j), message=f"Control character{plural}"),
            hint="Control characters are not allowed in Dewy source code (for security reasons). Please remove them."
        )


# TODO: other known error cases
known_multiple_matched_error_cases: list[MultipleMatchedErrorCase] = [
    ambiguous_number_or_identifier_in_parametric_string_escape,
]
known_no_match_error_cases: list[NoMatchErrorCase] = [
    shift_operator_inside_type_param,
    illegal_control_chars,
]


def collect_remaining_context_errors(ctx_stack: list[Context], max_pos:int|None=None) -> list[Error]:
    srcfile = ctx_stack[0].srcfile
    src = srcfile.body
    max_pos = len(src) if max_pos is None else min(max_pos, len(src))
    
    error_stack = []
    for ctx in reversed(ctx_stack):
        match ctx:
            case StringBody(opening_quote=o):
                error_stack.append(Error(srcfile, title="Missing string closing quote", pointer_messages=[
                    Pointer(span=o.loc, message="String opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message="String body"),
                    Pointer(span=Span(max_pos, max_pos), message="End without closing quote"),
                ], hint=f"Did you forget a `{o.src}`?"))
            case RawStringBody(opening_quote=o):
                error_stack.append(Error(srcfile, title="Missing raw string closing quote", pointer_messages=[
                    Pointer(span=o.loc, message="Raw string opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message="Raw string body"),
                    Pointer(span=Span(max_pos, max_pos), message="End without closing quote"),
                ], hint=f"Did you forget a `{o.src[1:]}`?"))
            case BlockBody(opening_delim=o):
                possible_closers = '`}`' if isinstance(o, (LeftCurlyBrace, ParametricStringEscape)) else '`]` or `)`'
                error_stack.append(Error(srcfile, title="Missing block closing delimiter", pointer_messages=[
                    Pointer(span=o.loc, message="Block opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message="Block body"),
                    Pointer(span=Span(max_pos, max_pos), message="End without closing delimiter"),
                ], hint=f"Did you forget a {possible_closers}?"))
            case TypeBody(opening_delim=o):
                error_stack.append(Error(srcfile, title="Missing type block closing chevron", pointer_messages=[
                    Pointer(span=o.loc, message="Type block opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message="Type block body"),
                    Pointer(span=Span(max_pos, max_pos), message="End without closing delimiter"),
                ], hint="Did you forget a `>`?"))
            case BasedStringBody(opening_quote=o):
                error_stack.append(Error(srcfile, title="Missing based-string closing quote", pointer_messages=[
                    Pointer(span=o.loc, message="Based string opened here"),
                    Pointer(span=Span(o.loc.stop, max_pos), message="Based string body"),
                    Pointer(span=Span(max_pos, max_pos), message="End without closing quote"),
                ], hint=f"Did you forget a `{o.src[2:]}`?"))
            case Root(): ... # root isn't an error (unless it somehow isn't the final context, but that should never happen)
            case _:
                pdb.set_trace()
                # unreachable (unless you added a new context type and forgot to add a case for it)
                raise NotImplementedError(f"INTERNAL ERROR: unhandled context: {ctx=}")
    
    return error_stack


##### TOKENIZER MAIN LOOP #####
# The main `tokenize` function drives the context-sensitive, declarative
# tokenization process described in the module docstring.
@cache
def get_allowed_tokens(ctx_type: type[Context]) -> list[type[Token]]:
    """For a given context type, return all token types that are allowed in that context. Cached for performance
    WARNING: because this is cached, creating new Token classes after this is called may not be reflected in the cached result
    """
    return [t for t in descendants(Token) if ctx_type in t.valid_contexts]

def tokenize(srcfile: SrcFile) -> list[Token]:
    tokens: list[Token] = []
    ctx_stack: list[Context] = [Root(srcfile, tokens_so_far=tokens)]
    ctx_history: list[Context] = []
    src = srcfile.body

    i = 0
    error_count = 0
    while i < len(src):
        # try to eat all allowed tokens at the current position
        ctx = ctx_stack[-1]
        allowed_tokens = get_allowed_tokens(type(ctx))
        matches = [(token_cls.eat(src[i:], ctx), token_cls) for token_cls in allowed_tokens]                

        # filter out matches that didn't eat anything
        matches = [(length, token_cls) for length, token_cls in matches if length is not None]

        # filter matches shorter than the longest match
        matches = sorted(matches, key=lambda x: x[0], reverse=True)
        longest_match_length = matches[0][0] if len(matches) > 0 else 0
        matches = [match for match in matches if match[0] == longest_match_length]

        # filter matches by precedence if any precedence rules apply
        match_types = [match[1] for match in matches]
        if len(matches) > 1:
            to_filter: set[type[Token]] = set()
            for Higher, Lower in token_precedence:
                if Higher in match_types and Lower in match_types:
                    to_filter.add(Lower)
            matches = [match for match in matches if match[1] not in to_filter]

        # if there are still multiple matches, it's an error
        if len(matches) > 1:
            # see if it matches a known error case
            errors = [error_case(src, i, tokens, ctx_stack, ctx_history, matches) for error_case in known_multiple_matched_error_cases]
            errors = list(filter(None, errors))
            if len(errors) > 0:
                error_count += len(errors)
                for error in errors:
                    print(error)
                break
            
            # fallback generic error
            error_count += 1
            match_names = ', '.join([match[1].__name__ for match in matches])
            error = Error(
                srcfile=srcfile,
                title=f"multiple tokens matched (fallback error case). Context={ctx.__class__.__name__}",
                pointer_messages=Pointer(span=Span(i, i+longest_match_length), message=f"multiple tokens matched at span [{i}..{i+longest_match_length}): {match_names}"),
                hint="disambiguation rules currently can't handle this case.\n1) Please manually disambiguate\n2) Probably this case should get a dedicated error function\n   consider opening an issue https://github.com/david-andrew/dewy-lang/issues"
            )
            print(error)    
            break
        
        # if there are no matches, it's an error
        if len(matches) == 0:
            # see if it matches a known error case
            errors = [error_case(src, i, tokens, ctx_stack, ctx_history) for error_case in known_no_match_error_cases]
            errors = list(filter(None, errors))
            if len(errors) > 0:
                error_count += len(errors)
                for error in errors:
                    print(error)
                break     
            # TODO: probably a better way to handle would be for checking if any upper contexts support the next token
            # potentially could use as a trick to recover/resynchronize and parse more tokens
            # TBD: what about the other way around, e.g. if the user didn't open a context they are trying to close?
            # could check what contexts support the next token--starts to get pretty heavy / complex
            error_count += 1
            error = Error(
                srcfile=srcfile,
                title=f"no valid token matched. Context={ctx.__class__.__name__}",
                pointer_messages=Pointer(span=Span(i, i), message=f"no valid token at position {i}: {truncate(first_line(src[i:]))}"),
            )
            print(error)
            break

        # add the token to the list of tokens
        length, token_cls = matches[0]
        token = token_cls(src[i:i+length], Span(i, i+length), len(tokens))
        action = token.action_on_eat(ctx)
        if action is not None:
            if isinstance(action, Push):
                ctx_stack.append(action.ctx)
            elif isinstance(action, Pop):
                ctx_history.append(ctx_stack.pop())
            else:
                # unreachable
                raise ValueError(f"INTERNAL ERROR: invalid context action: {action=}. Expected Push or Pop")
        tokens.append(token)
        i += length
    
    # pop any remaining rest-of-file string if present
    if len(ctx_stack) == 2 and isinstance(ctx_stack[-1], StringBody) and isinstance(ctx_stack[-1].opening_quote, RestOfFileStringQuote):
        ctx_stack.pop()
    if len(ctx_stack) == 2 and isinstance(ctx_stack[-1], RawStringBody) and isinstance(ctx_stack[-1].opening_quote, RawRestOfFileStringQuote):
        ctx_stack.pop()

    # ensure that the final context is a root 
    if not isinstance(ctx_stack[-1], Root):
        error_stack = collect_remaining_context_errors(ctx_stack)
        error_count += len(error_stack)
        for error in error_stack:
            print(error)
        print("-"*80)
        print(tokens_to_report(tokens, srcfile, {Whitespace}))

    # if there were errors, exit with an error code
    if error_count > 0:
        exit(1)
    
    return tokens

def tokens_to_report(tokens: list[Token], srcfile: SrcFile, blacklist: set[type[Token]] = set()) -> Info:
    """Convert a list of tokens to a report of the tokens consumed so far."""
    return Info(
        srcfile=srcfile,
        title="Tokens consumed so far",
        pointer_messages=[Pointer(
            span=token.loc,
            message=f"{token.__class__.__name__}",
            color=hash(token.__class__)
        ) for token in tokens if token.__class__ not in blacklist],
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
    try:
        tokens = tokenize(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)

    # to print out report of all tokens eaten    
    print(tokens_to_report(tokens, srcfile, {Whitespace}))

if __name__ == '__main__':
    test()