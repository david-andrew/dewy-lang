from .errors import Span, Info, Error, SrcFile, Pointer
from .utils import truncate, descendants, ordinalize, first_line
from typing import TypeAlias, ClassVar, get_origin, get_args, Union, Protocol
from types import UnionType
from dataclasses import dataclass
from abc import ABC, abstractmethod

import pdb

##### CONTEXT CLASSES #####

@dataclass
class Context(ABC):
    srcfile: SrcFile

class Root(Context): ...

@dataclass
class StringBody(Context):
    opening_quote: 'StringQuote'

@dataclass
class RawStringBody(Context):
    opening_quote: 'RawStringQuote'

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

whitespace = {' ', '\t', '\n', '\r'} # TBD if we need \f and \v

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



symbolic_operators = sorted([
    '~', '@', '`',
    '?', ';',
    '+', '-', '*', '/', '//', '^',
    '=?', '>?', '<?', '>=?', '<=?', 'in?', 'is?', 'isnt?', '<=>',
    '|', '&', '??',
    '=', '::', ':=' # not a walrus operator. `x:=y` is sugar for `let x=y` (TODO: move this description to where ever we describe all operators, e.g. docs)
    '@?',
    '|>', '<|', '=>',
    '->', '<->'
    '.', '..', '...', ',', ':', ':>',
], key=len, reverse=True)

# shift operators are not allowed in type groups
shift_operators = sorted(['<<', '>>', '<<<', '>>>', '<<!', '!>>'], key=len, reverse=True)


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
BodyOrRawStringContexts: TypeAlias = Root | BlockBody | TypeBody | StringBody | RawStringBody

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
        """
        if src[0] not in start_characters:
            return None
        i = 1
        while i < len(src) and src[i] in continue_characters:
            i += 1
        return i


class SymbolicOperator(Token[GeneralBodyContexts]):
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """symbolic operators are any sequence of characters in the symbolic_operators set"""
        for op in symbolic_operators:
            if src.startswith(op):
                return len(op)
        return None


class ShiftOperator(Token[BodyWithoutTypeContexts]):
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
            i, _ = Identifier.eat(src[1:])
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


class StringQuote(Token[BodyOrRawStringContexts]):
    matching_quote: 'StringQuote' = None

    @staticmethod
    def eat(src:str, ctx:BodyOrRawStringContexts) -> int|None:
        """string quotes are any odd-length sequence of either all single or all double quotes"""
        # only match if the first character is a quote
        if src[0] not in '\'"':
            return None
        
        # in a string body, the only kind of quote that can be matched is the matching closing quote
        if isinstance(ctx, StringBody):
            if not src.startswith(ctx.opening_quote.src):
                return None
            return len(ctx.opening_quote.src)
        
        # in a raw string body, see if we match the opening quote (minus the r prefix)
        if isinstance(ctx, RawStringBody):
            if not src.startswith(ctx.opening_quote.src[1:]):
                return None
            return len(ctx.opening_quote.src[1:])

        # match 2 quotes at a time
        i = 1
        quote = src[0]
        while src[i:].startswith(quote * 2):
            i += 2
        
        # if total is an even, this indicates empty string
        # eat just the opening quote
        if src[i:].startswith(quote):
            return (i + 1) // 2

        return i
    
    def action_on_eat(self, ctx:BodyOrRawStringContexts) -> ContextAction:
        
        # inside a string body, a quote closes the string
        if isinstance(ctx, StringBody):
            if ctx.opening_quote.src == self.src:
                self.matching_quote = ctx.opening_quote
                self.matching_quote.matching_quote = self
                return Pop()
            # unreachable
            raise ValueError(f"INTERNAL ERROR: attempted to eat StringQuote in a string body, but can only match the closing quote. {ctx.opening_quote.src=} {self.src=}")
        
        # inside a raw string body, a quote closes the raw string
        if isinstance(ctx, RawStringBody):
            if ctx.opening_quote.src[1:] == self.src:
                self.matching_quote = ctx.opening_quote
                self.matching_quote.matching_quote = self
                return Pop()
            # unreachable
            raise ValueError(f"INTERNAL ERROR: attempted to eat RawStringQuote in a raw string body, but can only match the closing quote. {ctx.opening_quote.src[1:]=} {self.src=}")
        
        # All other contexts, String quote opens a regular string body (not raw string)
        return Push(StringBody(ctx.srcfile, self))


class StringChars(Token[StringBody]):
    @staticmethod
    def eat(src:str, ctx:StringBody) -> int|None:
        """regular characters are anything except for the delimiter, an escape sequence, or a block opening"""
        i = 0
        while i < len(src) and not src[i:].startswith(ctx.opening_quote.src) and src[i] not in r'\{':
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


class RawStringQuote(Token[GeneralBodyContexts]):
    matching_quote: 'StringQuote' = None
    
    @staticmethod
    def eat(src:str, ctx:GeneralBodyContexts) -> int|None:
        """raw string quotes are r followed by any odd-length sequence of either all single or all double quotes"""
        if not src.startswith('r"') and not src.startswith("r'"):
            return None
        i = StringQuote.eat(src[1:], ctx)  # eat the quote without the r prefix
        if i is None:
            # unreachable
            raise ValueError(f"INTERNAL ERROR: attempted to eat RawStringQuote in a non-raw string body. {ctx=}")
        
        return i + 1
    
    def action_on_eat(self, ctx:GeneralBodyContexts): return Push(RawStringBody(ctx.srcfile, self))


class RawStringChars(Token[RawStringBody]):
    @staticmethod
    def eat(src:str, ctx:RawStringBody) -> int|None:
        """regular characters are anything except for the delimiter"""
        i = 0
        while i < len(src) and not src[i:].startswith(ctx.opening_quote.src[1:]):
            i += 1
        
        return i or None


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
            """
            TODO: special cases to check for and emit error messages:
            - no recognized token. next=`>`, previous was `>` and previous ctx was TypeBody ==> appears you tried to use a shift operator inside a type param. wrap the shift expression in ()
            """

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
        pointer_messages=[Pointer(span=token.loc, message=f"{token.__class__.__name__}") for token in tokens]
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