from abc import ABC
import inspect
from typing import Callable, Type, Generator
from types import UnionType
from functools import lru_cache

import pdb

#### DEBUG rich traceback printing ####
from rich import traceback, print
traceback.install(show_locals=True)



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


def wrap_coords(method:Callable):
    def wrapped_method(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        if isinstance(result, str) and len(result) == len(self):
            custom_str = CoordString(result)
            custom_str.row_col_map = self.row_col_map
            return custom_str
        else:
            raise ValueError("coord_string_method must return a string of the same length as the original string")
        return result

    return wrapped_method

def fail_coords(method:Callable):
    def wrapped_method(self, *args, **kwargs):
        raise ValueError(f"coord_string_method {method} cannot be called on a CoordString, as it will not return a CoordString")
    return wrapped_method


class CoordString(str):
    """
    Drop-in replacement for str that keeps track of the coordinates of each character in the string

    Identical to normal strings, but attaches the `row_col(i:int) -> tuple[int, int]` method
    which returns the (row, column) of the character at index i

    Args:
        anchor (tuple[int,int], optional): The row and column of the top left of the string. Defaults to (0, 0).
    """
    def __new__(cls, *args, anchor:tuple[int,int]=(0, 0), **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        row, col = anchor
        self.row_col_map = self._generate_row_col_map(row, col)

        return self

    def _generate_row_col_map(self, row=0, col=0):
        row_col_map = []
        for c in self:
            if c == '\n':
                row_col_map.append((row, col))
                row += 1
                col = 0
            else:
                row_col_map.append((row, col))
                col += 1
        return row_col_map

    def __getitem__(self, key):
        if isinstance(key, slice):
            sliced_str = super().__getitem__(key)
            sliced_row_col_map = self.row_col_map[key]
            custom_str = CoordString(sliced_str)
            custom_str.row_col_map = sliced_row_col_map
            return custom_str
        return super().__getitem__(key)

    def row_col(self, index):
        return self.row_col_map[index]

    #wrappers for string methods that should return CoordStrings
    @wrap_coords
    def capitalize(self): return super().capitalize()

    @wrap_coords
    def casefold(self): return super().casefold()

    @wrap_coords
    def lower(self): return super().lower()

    @wrap_coords
    def upper(self): return super().upper()

    @wrap_coords
    def swapcase(self): return super().swapcase()

    @wrap_coords
    def title(self): return super().title()

    @wrap_coords
    def translate(self, table): return super().translate(table)

    @wrap_coords
    def replace(self, old, new, count=-1): return super().replace(old, new, count)

    #TODO: some of these could be wrapped
    @fail_coords
    def center(self, *args, **kwargs): ...

    @fail_coords
    def expandtabs(self, *args, **kwargs): ...

    @fail_coords
    def ljust(self, *args, **kwargs): ...

    @fail_coords
    def lstrip(self, *args, **kwargs): ...

    @fail_coords
    def rstrip(self, *args, **kwargs): ...

    @fail_coords
    def strip(self, *args, **kwargs): ...

    @fail_coords
    def zfill(self, *args, **kwargs): ...





#TODO: maybe make adding this string with other regular str illegal





class Token(ABC):
    def __repr__(self) -> str:
        """default repr for tokens is just the class name"""
        return f"<{self.__class__.__name__}>"

class WhiteSpace_t(Token):
    def __init__(self, _): ...

class Juxtapose_t(Token):
    def __init__(self, _): ...

class Keyword_t(Token):
    def __init__(self, src:str):
        self.src = src.lower()
    def __repr__(self) -> str:
        return f"<Keyword: {self.src}>"

class Identifier_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Identifier: {self.src}>"
    
class Hashtag_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Hashtag: {self.src}>"

class Block_t(Token):
    def __init__(self, body:list[Token], left:str, right:str):
        self.body = body
        self.left = left
        self.right = right
    def __repr__(self) -> str:
        body_str = ', '.join(repr(token) for token in self.body)
        return f"<Block: {self.left}{body_str}{self.right}>"
    
class TypeParam_t(Token):
    def __init__(self, body:list[Token]):
        self.body = body
    def __repr__(self) -> str:
        body_str = ', '.join(repr(token) for token in self.body)
        return f"<TypeParam: `<{body_str}>`>"

class Escape_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Escape: {self.src}>"

class RawString_t(Token):
    def __init__(self, body:str):
        self.body = body
    def __repr__(self) -> str:
        return f"<RawString: {self.body}>"

class String_t(Token):
    def __init__(self, body:list[str|Escape_t|Block_t]):
        self.body = body
    def __repr__(self) -> str:
        return f"<String: {self.body}>"
    
# class Number_t(Token, ABC):...
    
class Integer_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Integer: {self.src}>"
    
class BasedNumber_t(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<BasedNumber: {self.src}>"

class Operator_t(Token):
    def __init__(self, op:str):
        self.op = op
    def __repr__(self) -> str:
        return f"<Operator: `{self.op}`>"
    
class ShiftOperator_t(Token):
    def __init__(self, op:str):
        self.op = op
    def __repr__(self) -> str:
        return f"<ShiftOperator: `{self.op}`>"

class Comma_t(Token):
    def __init__(self, src:str):
        self.src = src

class DotDot_t(Token):
    def __init__(self, src:str):
        self.src = src


    


# identify token classes that should take precedence over others when tokenizing
# each row is a list of token types that are confusable in their precedence order. e.g. [Keyword, Unit, Identifier] means Keyword > Unit > Identifier
# only confusable token classes need to be included in the table
precedence_table = [
    [Keyword_t, Operator_t, DotDot_t, Identifier_t],
]
precedence = {cls: len(row)-i for row in precedence_table for i, cls in enumerate(row)}

# mark which tokens cannot be repeated in a list of tokens. E.g. whitespace should always be merged into a single token
idempotent_tokens = {
    WhiteSpace_t
}

# paired delimiters for blocks, ranges, groups, etc.
pair_opening_delims = '{(['
pair_closing_delims = '})]'

#list of all operators sorted from longest to shortest
unary_prefix_operators = {'+', '-', '*', '/', 'not', '@', '...'}
unary_postfix_operators = {'?', '...'}
binary_operators = {
        '+', '-', '*', '/', '%', '^',
        '=?', '>?', '<?', '>=?', '<=?', 'in?', '<=>',
        '|', '&',
        'and', 'or', 'nand', 'nor', 'xor', 'xnor', '??',
        '=', ':=', 'as',
        '@?',
        '|>', '=>',
        '->', '<->', '<-',
        '.', ':'
}
operators = sorted(
    [*(unary_prefix_operators | unary_postfix_operators | binary_operators)],
    key=len,
    reverse=True
)
#TODO: may need to separate |> from regular operators since it may confuse type param
shift_operators = sorted(['<<', '>>', '<<<', '>>>', '<<<!', '!>>>'], key=len, reverse=True)
keywords = ['in', 'as', 'loop', 'lazy', 'if', 'else', 'return', 'express', 'transmute']

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


@peek_eat(Identifier_t)
def eat_identifier(src:str) -> int|None:
    """
    Eat an identifier, return the number of characters eaten
    
    identifiers are of the form  [a-zA-Z_] ([0-9a-zA-Z_?!$&]* [0-9a-zA-Z_!$&])?
    i.e. similar to regular identifiers, but allowing for ?!$& as well (though they may not end with ?)
    identifiers must start with a letter or underscore
    """
    if not src[0].isalpha() and src[0] != '_':
        return None

    i = 1
    while i < len(src) and (src[i].isalnum() or src[i] in '_?!$&'):
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
    """
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

    return tokens

def traverse_tokens(tokens:list[Token]) -> Generator[Token, None, None]:
    for token in tokens:
        yield token

        if isinstance(token, Block_t) or isinstance(token, TypeParam_t):
            for t in traverse_tokens(token.body):
                yield t
            continue
        
        if isinstance(token, String_t):
            for child in token.body:
                if isinstance(child, Token):
                    yield child
                if isinstance(child, Block_t):
                    for t in traverse_tokens(child.body):
                        yield t
            continue

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