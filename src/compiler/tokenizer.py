from abc import ABC
import inspect
from typing import Callable, Type, Generator
from types import UnionType
from functools import lru_cache
from utils import CoordString

import pdb

#### DEBUG rich traceback printing ####
try:
    from rich import traceback, print
    traceback.install(show_locals=True)
except:
    print('rich unavailable for import. using built-in printing')



"""
[tasks]
- clean up eat_block
    - general cleanup
    - break out eat_ matching into smaller functions?
    - figure out tie breaking process:
        1. prefer @full_eat over @peek_eat ---> TODO: implement
        2. prefer longest matches
        3. prefer higher precedence
        4. error
- make all tokens keep the source they come from (for error reporting/keeping track of row/col of the token)
"""




class Token(ABC):
    def __repr__(self) -> str:
        """default repr for tokens is just the class name"""
        return f"<{self.__class__.__name__}>"
    def __hash__(self) -> int:
        raise NotImplementedError(f'hash is not implemented for token type {type(self)}')
    def __eq__(self, __value: object) -> bool:
        raise NotImplementedError(f'equals is not implemented for token type {type(self)}')
    def __iter__(self) -> Generator['list[Token]', None, None]:
        """
        Iter is used by full_traverse_tokens for iterating over any contained tokens.
        e.g. Block_t.body TypeParam_t.body, String_t.body (interpolation blocks only), etc.
        """
        raise NotImplementedError(f'iter is not implemented for token type {type(self)}')

class WhiteSpace_t(Token):
    def __init__(self, _): ...

class Juxtapose_t(Token):
    def __init__(self, _): ...
    def __hash__(self) -> int:
        return hash(Juxtapose_t)
    def __eq__(self, other) -> bool:
        return isinstance(other, Juxtapose_t)

class Keyword_t(Token):
    def __init__(self, src:str):
        self.src = src.lower()
    def __repr__(self) -> str:
        return f"<Keyword_t: {self.src}>"
    def __hash__(self) -> int:
        return hash((Keyword_t, self.src))
    def __eq__(self, other) -> bool:
        return isinstance(other, Keyword_t) and self.src == other.src

class Identifier_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Identifier_t: {self.src}>"
    
class Hashtag_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Hashtag_t: {self.src}>"

class Block_t(Token):
    def __init__(self, body:list[Token], left:str, right:str):
        self.body = body
        self.left = left
        self.right = right
    def __repr__(self) -> str:
        body_str = ', '.join(repr(token) for token in self.body)
        return f"<Block_t: {self.left}{body_str}{self.right}>"
    def __iter__(self) -> Generator[list[Token], None, None]:
        yield self.body
    
class TypeParam_t(Token):
    def __init__(self, body:list[Token]):
        self.body = body
    def __repr__(self) -> str:
        body_str = ', '.join(repr(token) for token in self.body)
        return f"<TypeParam_t: `<{body_str}>`>"
    def __iter__(self) -> Generator[list[Token], None, None]:
        yield self.body

class Escape_t(Token):
    escape_map = {
        '\\n': '\n', '\\r': '\r', '\\t': '\t', '\\b': '\b', '\\f': '\f', '\\v': '\v', '\\a': '\a', '\\0': '\0', '\\\\': '\\'
    }
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Escape_t: {self.src}>"
    def to_str(self) -> str:
        """Convert the escape sequence to the character it represents"""

        #unicode escape (may be several characters long)
        if self.src.startswith('\\U') or self.src.startswith('\\u'):
            return chr(int(self.src[2:], 16))
        assert len(self.src) == 2 and self.src[0] == '\\', "internal error. Ill-posed escape sequence"

        #known escape sequence
        if self.src in self.escape_map:
            esc = self.escape_map[self.src]
            #construct a CoordString at the position of the original escape
            return CoordString.from_existing(esc, self.src[:len(esc)].row_col_map)

        #unknown escape sequence (i.e. just replicate the character)
        return self.src[1]



class RawString_t(Token):
    def __init__(self, body:str):
        self.body = body
    def __repr__(self) -> str:
        return f"<RawString_t: {self.body}>"
    def to_str(self) -> str:
        body = self.body
        if body.startswith('r"""') or body.startswith("r'''"):
            body = body[4:-3]
        elif body.startswith('r"') or body.startswith("r'"):
            body = body[2:-1]
        else:
            raise ValueError(f"Internal Error: unrecognized delimiters on raw string: {repr(self)}")
        return body

class String_t(Token):
    def __init__(self, body:list[str|Escape_t|Block_t]):
        self.body = body
    def __repr__(self) -> str:
        return f"<String_t: {self.body}>"
    def __iter__(self) -> Generator[list[Token], None, None]:
        for token in self.body:
            if isinstance(token, Block_t):
                yield token.body
    
# class Number_t(Token, ABC):...
    
class Integer_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Integer_t: {self.src}>"
    
class BasedNumber_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<BasedNumber_t: {self.src}>"

class Undefined_t(Token):
    def __init__(self, _): ...
    def __hash__(self) -> int:
        return hash(Undefined_t)
    def __eq__(self, other) -> bool:
        return isinstance(other, Undefined_t)
    def __repr__(self) -> str:
        return "<Undefined_t>"

class Void_t(Token):
    def __init__(self, _): ...
    def __hash__(self) -> int:
        return hash(Void_t)
    def __eq__(self, other) -> bool:
        return isinstance(other, Void_t)
    def __repr__(self) -> str:
        return "<Void_t>"

class End_t(Token):
    def __init__(self, _): ...
    def __hash__(self) -> int:
        return hash(End_t)
    def __eq__(self, other) -> bool:
        return isinstance(other, End_t)
    def __repr__(self) -> str:
        return "<End_t>"

class Boolean_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Boolean_t: {self.src}>"

class Operator_t(Token):
    def __init__(self, op:str):
        self.op = op
    def __repr__(self) -> str:
        return f"<Operator_t: `{self.op}`>"
    def __hash__(self) -> int:
        return hash((Operator_t, self.op))
    def __eq__(self, other) -> bool:
        return isinstance(other, Operator_t) and self.op == other.op
    
class ShiftOperator_t(Token):
    def __init__(self, op:str):
        self.op = op
    def __repr__(self) -> str:
        return f"<ShiftOperator_t: `{self.op}`>"
    def __hash__(self) -> int:
        return hash((ShiftOperator_t, self.op))
    def __eq__(self, other) -> bool:
        return isinstance(other, ShiftOperator_t) and self.op == other.op
    

class Comma_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __hash__(self) -> int:
        return hash(Comma_t)
    def __eq__(self, other) -> bool:
        return isinstance(other, Comma_t)

class DotDot_t(Token):
    def __init__(self, src:str):
        self.src = src


# #TODO: these should probably each be their own class/token, or a single class..
# these should all be case insensitive
# reserved_values = ['true', 'false', 'void', 'undefined', 'end'] 


    


# identify token classes that should take precedence over others when tokenizing
# each row is a list of token types that are confusable in their precedence order. e.g. [Keyword, Unit, Identifier] means Keyword > Unit > Identifier
# only confusable token classes need to be included in the table
precedence_table = [
    [Keyword_t, Undefined_t, Void_t, End_t, Boolean_t, Operator_t, DotDot_t, Identifier_t],
]
precedence = {cls: len(row)-i for row in precedence_table for i, cls in enumerate(row)}

# mark which tokens cannot be repeated in a list of tokens. E.g. whitespace should always be merged into a single token
idempotent_tokens = {
    WhiteSpace_t
}

# paired delimiters for blocks, ranges, groups, etc.
pair_opening_delims = '{(['
pair_closing_delims = '})]'

# which closing delimiters are allowed for each opening delimiter
valid_delim_closers = {
    '{': '}',
    '(': ')]',
    '[': '])',
    # '<': '>'
}

#list of all operators sorted from longest to shortest
unary_prefix_operators = {'+', '-', '*', '/', 'not', '@', '...'}
unary_postfix_operators = {'?', '`', ';'}
binary_operators = {
        '+', '-', '*', '/', '%', '^',
        '=?', '>?', '<?', '>=?', '<=?', 'in?', 'is?', 'isnt?', '<=>',
        '|', '&',
        'and', 'or', 'nand', 'nor', 'xor', 'xnor', '??',
        'else',
        '=', ':=', 'as', 'in', 'transmute',
        '@?',
        '|>', '<|', '=>',
        '->', '<->', '<-',
        '.', ':'
}
opchain_starters = {'+', '-', '*', '/', '%', '^'}
operators = sorted(
    [*(unary_prefix_operators | unary_postfix_operators | binary_operators)],
    key=len,
    reverse=True
)
#TODO: may need to separate |> from regular operators since it may confuse type param
shift_operators = sorted(['<<', '>>', '<<<', '>>>', '<<!', '!>>'], key=len, reverse=True)
keywords = ['loop', 'lazy', 'do', 'if', 'return', 'yield', 'async', 'await', 'import', 'from', 'let', 'const']
#TODO: what about language values, e.g. void, undefined, end, units, etc.? probably define at compile time, rather than in the compiler

# note that the prefix is case insensitive, so call .lower() when matching the prefix
# numbers may have _ as a separator (if _ is not in the set of digits)
number_bases = {
    '0b': {*'01'},                      #binary
    '0t': {*'012'},                     #ternary
    '0q': {*'0123'},                    #quaternary
    '0s': {*'012345'},                  #seximal
    '0o': {*'01234567'},                #octal
    '0d': {*'0123456789'},              #decimal
    '0z': {*'0123456789xeXE'},          #dozenal
    '0x': {*'0123456789abcdefABCDEF'},  #hexadecimal 
    '0u': {*'0123456789abcdefghijklmnopqrstuvABCDEFGHIJKLMNOPQRSTUV'},              #base 32 (duotrigesimal)
    '0r': {*'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'},      #base 36 (hexatrigesimal)
    '0y': {*'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!$'},    #base 64 (tetrasexagesimal)
}


# units = #actually units should probably not be specific tokens, but recognized identifiers since the user can make their own units



def peek_eat(cls:Type[Token], whitelist:list[Type[Token]]|None=None, blacklist:list[Type[Token]]|None=None):
    """
    Decorator for functions that eat tokens, but only return how many characters would make up the token. 
    Makes function return include constructor for token class that it tries to eat, in tupled with return.

    whitelist and blacklist can be used to specify parent token contexts that may or may not consume this type as a child
    """
    assert issubclass(cls, Token), f"cls must be a subclass of Token, but got {cls}"
    if whitelist is not None and blacklist is not None:
        raise ValueError("cannot specify both whitelist and blacklist")
    def decorator(eat_func:Callable[[str], int|None]):
        def wrapper(src:str) -> tuple[int|None, Type[Token]]:
            return eat_func(src), cls
        wrapper._is_peek_eat_decorator = True  # make it easy to check if a function has this decorator
        wrapper._eat_func = eat_func
        wrapper._token_cls = cls
        wrapper._whitelist = whitelist
        wrapper._blacklist = blacklist
        return wrapper
    return decorator

#TODO: full eat probably won't need to take the class as an argument, since the function will know how to construct the token itself
def full_eat(whitelist:list[Type[Token]]|None=None, blacklist:list[Type[Token]]|None=None):
    def decorator(eat_func:Callable[[str], tuple[int, Token] | None]):
        """
        Decorator for functions that eat tokens, and return the token itself if successful.
        TBD what this actually does...for now, largely keep unmodified, but attach the metadata to the wrapped function
        """
        # pull cls it from the return type of eat_func (which should be a Union[tuple[int, Token], None])
        cls = inspect.signature(eat_func).return_annotation.__args__[0].__args__[1]
        assert issubclass(cls, Token), f"cls must be a subclass of Token, but got {cls}"
        if whitelist is not None and blacklist is not None:
            raise ValueError("cannot specify both whitelist and blacklist")
        def wrapper(*args, **kwargs):
            return eat_func(*args, **kwargs), cls
        wrapper._is_full_eat_decorator = True  # make it easy to check if a function has this decorator
        wrapper._eat_func = eat_func
        wrapper._token_cls = cls
        wrapper._whitelist = whitelist
        wrapper._blacklist = blacklist

        return wrapper
    return decorator


def get_peek_eat_funcs_with_name() -> tuple[tuple[str, Callable]]:
    return tuple((name, func) for name, func in globals().items() if callable(func) and getattr(func, '_is_peek_eat_decorator', False))
def get_full_eat_funcs_with_name() -> tuple[tuple[str, Callable]]:
    return tuple((name, func) for name, func in globals().items() if callable(func) and getattr(func, '_is_full_eat_decorator', False))

def get_eat_funcs() -> tuple[Callable]:
    return tuple(func for name, func in get_peek_eat_funcs_with_name() + get_full_eat_funcs_with_name())

@lru_cache()
def get_contextual_eat_funcs(context:Type[Token]) -> tuple[Callable]:
    """Get all the eat functions that are valid in the given context"""
    return tuple(func for func in get_eat_funcs() if (func._whitelist is None or context in func._whitelist) and (func._blacklist is None or context not in func._blacklist))

@lru_cache()
def get_func_precedences(funcs:tuple[Callable]) -> tuple[int]:
    assert isinstance(funcs, tuple)
    return tuple(precedence.get(func._token_cls, 0) for func in funcs)


@peek_eat(WhiteSpace_t)
def eat_line_comment(src:str) -> int|None:
    """eat a line comment, return the number of characters eaten"""
    if src.startswith('//'):
        try:
            return src.index('\n') + 1
        except ValueError:
            return len(src)
    return None

@peek_eat(WhiteSpace_t)
def eat_block_comment(src:str) -> int|None:
    """
    Eat a block comment, return the number of characters eaten
    Block comments are of the form /{ ... }/ and can be nested.
    """
    if not src.startswith("/{"):
        return None

    nesting_level = 0
    i = 0

    while i < len(src):
        if src[i:].startswith('/{'):
            nesting_level += 1
            i += 2
        elif src[i:].startswith('}/'):
            nesting_level -= 1
            i += 2

            if nesting_level == 0:
                return i
        else:
            i += 1

    raise ValueError("unterminated block comment")
    # return None

@peek_eat(WhiteSpace_t)
def eat_whitespace(src:str) -> int|None:
    """Eat whitespace, return the number of characters eaten"""
    i = 0
    while i < len(src) and src[i].isspace():
        i += 1
    return i if i > 0 else None

@peek_eat(Keyword_t)
def eat_keyword(src: str) -> int | None:
    """
    Eat a reserved keyword, return the number of characters eaten

    #keyword = {in} | {as} | {loop} | {lazy} | {if} | {and} | {or} | {xor} | {nand} | {nor} | {xnor} | {not};# | {true} | {false}; 
    
    noting that keywords are case insensitive
    """

    max_len = max(len(keyword) for keyword in keywords)
    
    lower_src = src[:max_len].lower()
    for keyword in keywords:
        if lower_src.startswith(keyword):
            #TBD if we need to check that the next character is not an identifier character
            return len(keyword)

    return None



#TODO: expand the list of valid identifier characters
digits = set('0123456789')
alpha = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
greek = set('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρςστυφχψω')
misc = set('_?!$&°')

start_characters = (alpha | greek | misc) - {'?'}
continue_characters = (alpha | digits | greek | misc)


@peek_eat(Identifier_t)
def eat_identifier(src:str) -> int|None:
    """
    Eat an identifier, return the number of characters eaten

    Identifiers:
    - may not start with a number or a question mark
    - may not end with a question mark
    - may use (TODO enumerate the full chars list somewhere. for now copying from python)
    
    """
    if not src[0] in start_characters:
        return None

    i = 1
    while i < len(src) and src[i] in continue_characters:
        i += 1

    # while last character is ?, remove it
    while i > 1 and src[i-1] == '?':
        i -= 1

    return i



@peek_eat(Hashtag_t)
def eat_hashtag(src:str) -> int|None:
    """
    Eat a hashtag, return the number of characters eaten
    
    hashtags are special identifiers that start with #
    """

    if src.startswith('#'):
        i,_ = eat_identifier(src[1:])
        if i is not None:
            return i + 1
        
    return None


@peek_eat(Escape_t, whitelist=[String_t])
def eat_escape(src:str) -> int|None:
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
    
    or a \ followed by an unknown character. In this case, the escape converts to just the unknown character
    This is how to insert characters that are otherwise illegal inside a string, e.g. 
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
        while i < len(src) and src[i].isxdigit():
            i += 1
        if i == 2:
            raise ValueError("invalid unicode escape sequence")
        return i

    # if src[1] in 'nrtbfva0':
    #     return 2

    #all other escape sequences (known or unknown) are just a single character
    return 2


@full_eat()
def eat_string(src:str) -> tuple[int, String_t] | None:
    r"""
    strings are delimited with either single (') or double quotes (")
    the character portion of a string may contain any character except the delimiter, \, or {.
    strings may be multiline
    strings may contain escape sequences of the form \s where s is either a known escape sequence or a single character
    strings may interpolation blocks which open with { and close with }

    Tokenizing of escape sequences and interpolation blocks is handled as sub-tokenization task via eat_block and eat_escape

    returns the number of characters eaten and an instance of the String token, containing the list of tokens/string chunks/escape sequences
    """
    
    #determine the starting delimiter, or exit if there is none
    if src.startswith('"""') or src.startswith("'''"):
        delim = src[:3]
        i = 3
    elif src.startswith('"') or src.startswith("'"):
        delim = src[0]
        i = 1
    else:
        return None
    
    #keep track of chunks, and the start index of the current chunk
    chunk_start = i
    body = []

    # add character sequences, escapes, and block sections until the end of the string
    while i < len(src) and not src[i:].startswith(delim):
        
        #regular characters
        if src[i] not in '\\{':
            i += 1
            continue

        #add the previous chunk before handling the escape/interpolation block
        if i > chunk_start:
            body.append(src[chunk_start:i])

        if src[i] == '\\':
            res, _ = eat_escape(src[i:])
            if res is None:
                raise ValueError("invalid escape sequence")
            body.append(Escape_t(src[i:i+res]))
            i += res

        else: # src[i] == '{':
            assert src[i] == '{', "internal error"
            res, _ = eat_block(src[i:])
            if res is None:
                raise ValueError("invalid block")
            n_eaten, block = res
            body.append(block)
            i += n_eaten
        
        #update the chunk start
        chunk_start = i
            

    if i == len(src):
        raise ValueError("unterminated string")
    
    #add the final chunk
    if i > chunk_start:
        body.append(src[chunk_start:i])
    
    return i + len(delim), String_t(body)



@peek_eat(RawString_t)
def eat_raw_string(src:str) -> int|None:
    """
    raw strings start with `r`, followed by a delimiter, one of ' " ''' or \"""
    raw strings may contain any character except the delimiter.
    Escapes and interpolations are ignored.
    The string ends at the first instance of the delimiter
    """
    if not src.startswith('r'):
        return None
    i = 1

    if src[i:].startswith('"""') or src[i:].startswith("'''"):
        delim = src[i:i+3]
        i += 3
    elif src[i:].startswith('"') or src[i:].startswith("'"):
        delim = src[i]
        i += 1
    else:
        return None

    while i < len(src) and not src[i:].startswith(delim):
        i += 1

    if i == len(src):
        raise ValueError("unterminated raw string")

    return i + len(delim)


@peek_eat(Integer_t)
def eat_integer(src:str) -> int|None:
    """
    eat an integer, return the number of characters eaten
    integers are of the form [0-9]+
    """
    i = 0
    while i < len(src) and src[i].isdigit():
        i += 1
    return i if i > 0 else None


@peek_eat(BasedNumber_t)
def eat_based_number(src:str) -> int|None:
    """
    eat a based number, return the number of characters eaten

    based numbers have a (case-insensitive) prefix (0p) identifying the base, and (case-sensitive) allowed digits
    """
    try:
        digits = number_bases[src[:2].lower()]
    except KeyError:
        return None
    
    i = 2
    while i < len(src) and src[i] in digits or src[i] == '_':
        i += 1

    return i if i > 2 else None


@peek_eat(Undefined_t)
def eat_undefined(src:str) -> int|None:
    """
    eat the undefined token, return the number of characters eaten
    """
    sample = src[:9].lower()
    if sample.startswith('undefined'):
        return 9
    return None


@peek_eat(Void_t)
def eat_void(src:str) -> int|None:
    """
    eat the void token, return the number of characters eaten
    """
    sample = src[:4].lower()
    if sample.startswith('void'):
        return 4
    return None


@peek_eat(End_t)
def eat_end(src:str) -> int|None:
    """
    eat the end token, return the number of characters eaten
    """
    sample = src[:3].lower()
    if sample.startswith('end'):
        return 3
    return None


@peek_eat(Boolean_t)
def eat_boolean(src:str) -> int|None:
    """
    eat a boolean, return the number of characters eaten

    booleans are either true or false (case-insensitive)
    """
    sample = src[:5].lower()
    if sample.startswith('true'):
        return 4
    elif sample.startswith('false'):
        return 5

    return None


@peek_eat(Operator_t)
def eat_operator(src:str) -> int|None:
    """
    eat a unary or binary operator, return the number of characters eaten

    picks the longest matching operator

    see `operators` for full list of operators
    """
    for op in operators:
        if src.startswith(op):
            return len(op)
    return None

@peek_eat(ShiftOperator_t, blacklist=[TypeParam_t])
def eat_shift_operator(src:str) -> int|None:
    """
    eat a shift operator, return the number of characters eaten

    picks the longest matching operator. 
    Shift operators are not allowed in type parameters, e.g. `>>` is not recognized in `Foo<Bar<Baz<T>>, U>`

    see `shift_operators` for full list of operators
    """
    for op in shift_operators:
        if src.startswith(op):
            return len(op)
    return None

@peek_eat(Comma_t)
def eat_comma(src:str) -> int|None:
    """
    eat a comma, return the number of characters eaten
    """
    return 1 if src.startswith(',') else None


@peek_eat(DotDot_t)
def eat_dotdot(src:str) -> int|None:
    """
    eat a dotdot, return the number of characters eaten
    """
    return 2 if src.startswith('..') else None



class EatTracker:
    i: int
    tokens: list[Token]


@full_eat()
def eat_type_param(src:str) -> tuple[int, TypeParam_t] | None:
    """
    eat a type parameter, return the number of characters eaten and an instance of the TypeParam token

    type parameters are of the form <...> where ... is a sequence of tokens. 
    Type parameters may not start with `<<` or contain any shift operators (`<<`, `<<<`, `>>`, `>>>`)
    Internally encountered shift operators are considered to be delimiters for the type parameter
    """
    if not src.startswith('<') or src.startswith('<<'):
        return None
    
    i = 1
    body: list[Token] = []

    while i < len(src) and src[i] != '>':
        
        funcs = get_contextual_eat_funcs(TypeParam_t)
        precedences = get_func_precedences(funcs)
        res = get_best_match(src[i:], funcs, precedences)

        if res is None:
            return None        
        n_eaten, token = res

        if isinstance(token, Token):
            #add the already-eaten token to the list of tokens
            body.append(token)
        else:
            #add a new instance of the token to the list of tokens (handling idempotent token cases)
            token_cls = token
            if not body or token_cls not in idempotent_tokens or not isinstance(body[-1], token_cls):
                body.append(token_cls(src[i:i+n_eaten]))

        #increment the index
        i += n_eaten


    if i == len(src):
        return None
    
    return i + 1, TypeParam_t(body)
    



@full_eat()
def eat_block(src:str, tracker:EatTracker|None=None) -> tuple[int, Block_t] | None:
    """
    Eat a block, return the number of characters eaten and an instance of the Block token

    blocks are { ... } or ( ... ) and may contain sequences of any other tokens including other blocks

    if return_partial is True, then returns (i, body) in the case where the eat process fails, instead of None
    """
    
    if not src or src[0] not in pair_opening_delims:
        return None
    
    # save the opening delimiter
    left = src[0]
    
    i = 1
    body: list[Token] = []

    if tracker:
        tracker.i = i
        tracker.tokens = body

    while i < len(src) and src[i] not in pair_closing_delims:
        #run all root eat functions
        #if multiple, resolve for best match (TBD... current is longest match + precedence)
        #if no match, return None


        ########### TODO: probably break this inner part into a function that eats the next token, given a list of eat functions
        ###########       could also think about ways to specify other multi-match resolutions, other than longest match + precedence...
        #run all the eat functions on the current src
        funcs = get_contextual_eat_funcs(Block_t)
        precedences = get_func_precedences(funcs)
        res = get_best_match(src[i:], funcs, precedences)

        #if we didn't match anything, return None
        if res is None:
            return None
        
        n_eaten, token = res
        
        if isinstance(token, Token):
            #add the already-eaten token to the list of tokens
            body.append(token)
        else:
            #add a new instance of the token to the list of tokens (handling idempotent token cases)
            token_cls = token
            if not body or token_cls not in idempotent_tokens or not isinstance(body[-1], token_cls):
                body.append(token_cls(src[i:i+n_eaten]))

        #increment the index
        i += n_eaten
        if tracker:
            tracker.i = i

    if i == len(src):
        if tracker: #only return an exception for the top level block. nested blocks can return None
            raise ValueError("unterminated block") 
        return None
    
    # closing delim (doesn't need to match opening delim)
    right = src[i]
    assert left in pair_opening_delims and right in pair_closing_delims, f"invalid block delimiters: {left} {right}"

    #include closing delimiter in character count
    i += 1
    if tracker:
        tracker.i = i

    return i, Block_t(body, left=left, right=right)



def get_best_match(src:str, eat_funcs:list, precedences:list[int]) -> tuple[int, Type[Token]|Token]|None:
    #TODO: handle selecting between full_eat and peek_eat functions that were successful...
    #      general, just need to clarify the selection order precedence

    #may return none if no match
    #may return (i, token_cls) if peek match
    #may return (i, token) if full match

    matches = [eat_func(src) for eat_func in eat_funcs]

    #find the longest token that matched. if multiple tied for longest, use the one with the highest precedence.
    #raise an error if multiple tokens tied, and they have the same precedence
    def key(x):
        (res, _cls), precedence = x
        if res is None:
            return 0, precedence
        if isinstance(res, tuple):
            res, _token = res #full_eat functions return a tuple of (num_chars_eaten, token)
        return res, precedence

    matches = [*zip(matches, precedences)]
    best = max(matches, key=key)
    ties = [match for match in matches if key(match) == key(best)]
    if len(ties) > 1:
        raise ValueError(f"multiple tokens matches tied {[match[0][1].__name__ for match in ties]}: {repr(src)}\nPlease disambiguate by providing precedence levels for these tokens.")

    (res, token_cls), _ = best
    
    # force the type annotations
    res: tuple[int, Token]|int|None 
    token_cls: type[Token]

    if res is None:
        return None
    
    if isinstance(res, int):
        return res, token_cls
    
    if isinstance(res, tuple):
        return res
    
    raise ValueError(f"Internal Error: invalid return type from eat function: {res}")



def tokenize(src:str) -> list[Token]:

    # insert src into a block
    src = f'{{\n{src}\n}}'

    #convert string to a coordinate string (for keeping track of row/col numbers)
    src = CoordString(src, anchor=(-1, 0))

    # eat tokens for a block
    tracker = EatTracker()
    try:
        res, _cls = eat_block(src, tracker=tracker)
    except Exception as e:
        raise ValueError(f"failed to tokenize: ```{escape_whitespace(src[tracker.i:])}```.\nCurrent tokens: {tracker.tokens}") from e

    # check if the process failed
    if res is None:
        raise ValueError(f"failed to tokenize: ```{escape_whitespace(src[tracker.i:])}```.\nCurrent tokens: {tracker.tokens}")

    (i, block) = res
    tokens = block.body

    # ensure that all blocks have valid open/close pairs
    validate_block_braces(tokens)

    return tokens

def full_traverse_tokens(tokens:list[Token]) -> Generator[tuple[int, Token, list[Token]], None, None]:
    """
    Walk all tokens recursively, allowing for modification of the tokens list as it is traversed.
    
    So long as modifications do not occur before the current token, this will safely iterate over all tokens.
    This will not yield string or escape chunks in strings, but will yield interpolated blocks.

    While traversing, the user can overwrite the current index by calling .send(new_index).

    e.g.
    ```python
    gen = full_traverse_tokens(tokens)
    for i, token, stream in gen:
        #do something with current token
        #...

        #maybe overwrite the current index
        if should_overwrite:
            gen.send(new_index)
    ```

    Do not call .send() twice in a row without calling next() in between. This will cause unexpected behavior.

    Args:
        tokens: the list of tokens to traverse

    Yields:
        i: the index of the current token in the current token list
        token: the current token
        stream: the current token list
    """

    i = 0

    while i < len(tokens):
        """
        1. get next token
        2. send current to user
        3. increment index (or overwrite it)
        4. recurse into blocks
        """

        # get the current token
        token = tokens[i]

        # send the current index to the user. possibly receive a new index to continue from
        overwrite_i = yield i, token, tokens

        # only calls to next() will continue execution. calls to .send do nothing wait
        if overwrite_i is not None:
            assert (yield) is None, ".send() may only be called once per iteration."
            i = overwrite_i
        else:
            i += 1

        # for tokens that have defined __iter__ methods, yield their contents
        try:
            for children in token:
                yield from full_traverse_tokens(children)
        except NotImplementedError:
            pass


def traverse_tokens(tokens:list[Token]) -> Generator[Token, None, None]:
    """
    Convenience function over full_traverse_tokens. Walk all tokens recursively
    
    Does not allow for modification of the tokens list as it is traversed.
    To modify during traversal, use `full_traverse_tokens` instead.

    Args:
        tokens: the list of tokens to traverse

    Yields:
        token: the current token
    """
    for _, token, _ in full_traverse_tokens(tokens):
        yield token



def validate_block_braces(tokens:list[Token]) -> None:
    """
    Checks that all blocks have valid open/close pairs.

    For example, ranges may have differing open/close pairs, e.g. [0..10), (0..10], etc.
    But regular blocks must have matching open/close pairs, e.g. { ... }, ( ... ), [ ... ]
    Performs some validation, without knowing if the block is a range or a block. 
    So more validation is needed when the actual block type is known.

    Raises:
        AssertionError: if a block is found with an invalid open/close pair
    """
    for token in traverse_tokens(tokens):
        if isinstance(token, Block_t):
            assert token.left in valid_delim_closers, f'INTERNAL ERROR: left block opening token is not a valid token. Expected one of {[*valid_delim_closers.keys()]}. Got \'{token.left}\''
            assert token.right in valid_delim_closers[token.left], f'ERROR: mismatched opening and closing braces. For opening brace \'{token.left}\', expected one of \'{valid_delim_closers[token.left]}\''
        

def validate_functions():

    # Validate the @peek_eat function signatures
    peek_eat_functions = get_peek_eat_funcs_with_name()
    for name, wrapper_func in peek_eat_functions:
        func = wrapper_func._eat_func
        signature = inspect.signature(func)
        param_types = [param.annotation for param in signature.parameters.values() if param.default is inspect.Parameter.empty]
        return_type = signature.return_annotation

        # Check if the function has the correct signature
        if len(param_types) != 1 or param_types[0] != str or return_type != int|None:
            pdb.set_trace()
            raise ValueError(f"{func.__name__} has an invalid signature: `{signature}`. Expected `(src: str) -> int | None`")

    # Validate the @full_eat function signatures
    full_eat_functions = get_full_eat_funcs_with_name()
    for name, wrapper_func in full_eat_functions:
        func = wrapper_func._eat_func
        signature = inspect.signature(func)
        param_types = [param.annotation for param in signature.parameters.values() if param.default is inspect.Parameter.empty]
        return_type = signature.return_annotation

        # Check if the function has the correct signature
        error_message = f"{func.__name__} has an invalid signature: `{signature}`. Expected `(src: str) -> tuple[int, Token] | None`"
        if not (isinstance(return_type, UnionType) and len(return_type.__args__) == 2 and type(None) in return_type.__args__):
            raise ValueError(error_message)
        A, B = return_type.__args__
        if B is not type(None):
            B, A = A, B
        if not (isinstance(A, type(tuple)) and len(A.__args__) == 2 and A.__args__[0] is int and issubclass(A.__args__[1], Token)):
            raise ValueError(error_message)        
        if len(param_types) != 1 or param_types[0] != str:
            pdb.set_trace()
            raise ValueError(error_message)

    # check for any functions that start with eat_ but are not decorated with @eat
    peek_eat_func_names = {name for name, _ in peek_eat_functions}
    full_eat_func_names = {name for name, _ in full_eat_functions}
    for name, func in globals().items():
        if name.startswith("eat_") and callable(func) and name not in peek_eat_func_names and name not in full_eat_func_names:
            raise ValueError(f"`{name}()` function is not decorated with @peek_eat or @full_eat")


def escape_whitespace(s:str):
    """convert a string to one where all non-space whitespace is escaped"""
    escape_map = {
        '\t': '\\t',
        '\r': '\\r',
        '\f': '\\f',
        '\v': '\\v',
        '\n': '\\n',
    }
    return ''.join(escape_map.get(c, c) for c in s)


def tprint(token:Token, level=0):
    """
    print a token with a certain indentation level.
    
    If tokens contain nested tokens, they will be printed recursively with an increased indentation level
    """
    print(f'{"    "*level}', end='')
    if isinstance(token, Block_t):
        print(f'<Block {token.left}{token.right}>')
        for t in token.body:
            tprint(t, level=level+1)
    elif isinstance(token, String_t):
        print(f'<String>')
        for t in token.body:
            tprint(t, level=level+1)
    elif isinstance(token, TypeParam_t):
        print(f'<TypeParam>')
        for t in token.body:
            tprint(t, level=level+1)
    else:
        print(token)
        


def test():
    import sys
    """simple test dewy program"""

    try:
        path = sys.argv[1]
    except IndexError:
        raise ValueError("Usage: `python tokenizer.py path/to/file.dewy>`")


    with open(path) as f:
        src = f.read()

    tokens = tokenize(src)
    print(f'matched tokens:')
    tprint(Block_t(left='{', right='}', body=tokens))
    # for t in tokens:
    #     tprint(t, level=1)




if __name__ == "__main__":
    validate_functions()
    test()