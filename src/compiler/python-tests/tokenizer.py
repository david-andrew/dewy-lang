#TODO:
# - we're just going to go back to the standard lexer/parser approach
#     tokenize

# for handling string interpolation:
# have string left and right halves as tokens, which can sandwich any number of expressions and internal strings
#    ^^^^^basically, tokenizing needs to have a context stack, which is the current type being parsed.^^^^^
#         if see a quote (and context is not string), add string onto stack


# everything is either a sequence or an operation. strip outside (lowest precedence) of tokens until we get to the middle



from abc import ABC
from enum import Enum, auto
import inspect
from typing import Callable, Type

import pdb

#### DEBUG rich traceback printing ####
from rich import traceback, print
traceback.install(show_locals=True)


#TODO: tbd how this gets used
#      context is useful to know which of the eat functions to use during tokenization
#      e.g. when inside a string, only eat_character, eat_escape, and eat_block
class Context(Enum):
    root = auto()
    block = auto()
    # string = auto()
    interpolation = auto()


class Token(ABC):
    def __repr__(self) -> str:
        """default repr for tokens is just the class name"""
        return f"<{self.__class__.__name__}>"

class WhiteSpace(Token):
    def __init__(self, _): ...

class Keyword(Token):
    def __init__(self, src:str):
        self.src = src.lower()
    def __repr__(self) -> str:
        return f"<Keyword: {self.src}>"

class Identifier(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Identifier: {self.src}>"
    
class Bind(Token):
    def __init__(self, _): ...

class Block(Token):
    def __init__(self, body:list[Token]):
        self.body = body
    def __repr__(self) -> str:
        return f"<Block: {self.body}>"

class Escape(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Escape: {self.src}>"

class String(Token):
    def __init__(self, body:list[str|Escape|Block]):
        self.body = body
    def __repr__(self) -> str:
        return f"<String: {self.body}>"
    


    


# identify token classes that should take precedence over others when tokenizing
# each row is a list of token types that are confusable in their precedence order. e.g. [Keyword, Unit, Identifier] means Keyword > Unit > Identifier
# only confusable token classes need to be included in the table
precedence_table = [
    [Keyword, Identifier],
]
precedence = {cls: len(row)-i for row in precedence_table for i, cls in enumerate(row)}

# mark which tokens cannot be repeated in a list of tokens. E.g. whitespace should always be merged into a single token
idempotent_tokens = {
    WhiteSpace
}


def eat(cls:Type[Token], context_free:bool=True):
    """
    Decorator for functions that eat tokens. 
    Makes function return include constructor for token class that it tries to eat, in tupled with return.
    """
    assert issubclass(cls, Token), f"cls must be a subclass of Token, but got {cls}"
    def decorator(eat_func:Callable[[str], int|None]):
        def wrapper(src:str) -> tuple[int|None, Type[Token]]:
            return eat_func(src), cls
        wrapper._context_free = context_free
        wrapper._is_eat_decorator = True  # make it easy to check if a function has this decorator
        wrapper._eat_func = eat_func
        wrapper._token_cls = cls
        return wrapper
    return decorator


@eat(WhiteSpace)
def eat_line_comment(src:str) -> int|None:
    """eat a line comment, return the number of characters eaten"""
    if src.startswith('//'):
        try:
            return src.index('\n') + 1
        except ValueError:
            return len(src)
    return None

@eat(WhiteSpace)
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

@eat(WhiteSpace)
def eat_whitespace(src:str) -> int|None:
    """Eat whitespace, return the number of characters eaten"""
    i = 0
    while i < len(src) and src[i].isspace():
        i += 1
    return i if i > 0 else None

@eat(Keyword)
def eat_keyword(src: str) -> int | None:
    """
    Eat a reserved keyword, return the number of characters eaten

    #keyword = {in} | {as} | {loop} | {lazy} | {if} | {and} | {or} | {xor} | {nand} | {nor} | {xnor} | {not};# | {true} | {false}; 
    
    noting that keywords are case insensitive
    """

    keywords = ['in', 'as', 'loop', 'lazy', 'if', 'and', 'or', 'xor', 'nand', 'nor', 'xnor', 'not']#, 'true', 'false'] #TBD if true/false are keywords
    max_len = max(len(keyword) for keyword in keywords)
    
    lower_src = src[:max_len].lower()
    for keyword in keywords:
        if lower_src.startswith(keyword):
            #TBD if we need to check that the next character is not an identifier character
            return len(keyword)

    return None


@eat(Identifier)
def eat_identifier(src:str) -> int|None:
    """
    Eat an identifier, return the number of characters eaten
    
    identifiers are of the form  [a-zA-Z_] [0-9a-zA-Z_?!$&]*
    """
    i = 0
    while i < len(src) and src[i].isalnum() or src[i] in '_?!$&':
        i += 1
    return i if i > 0 else None



@eat(Bind)
def eat_bind(src:str) -> int|None:
    """eat a bind operator, return the number of characters eaten"""
    if src.startswith('='):
        return 1
    return None


@eat(Escape, context_free=False)
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


@eat(String)
def eat_string(src:str) -> int|None:
    """
    strings are delimited with either single (') or double quotes (")
    the character portion of a string may contain any character except the delimiter, \, or {.
    strings may be multiline
    strings may contain escape sequences of the form \s where s is either a known escape sequence or a single character
    strings may interpolation blocks which open with { and close with }

    Tokenizing of escape sequences and interpolation blocks is handled as sub-tokenization task via eat_block and eat_escape
    """
    if not src[0] in '"\'':
        return None
    
    delim = src[0]
    i = 1
    while i < len(src):
        if src[i] == delim:
            return i + 1
        elif src[i] == '\\':
            res, _ = eat_escape(src[i:])
            if res is None:
                raise ValueError("invalid escape sequence")
            i += res
        elif src[i] == '{':
            res, _ = eat_block(src[i:])
            if res is None:
                raise ValueError("invalid interpolation block")
            i += res
        else:
            i += 1

#random note: if you for some reason needed to do a unicode escape followed by a character that happens to be a hex digit, you could do \u##{}#, where the empty block {} breaks the hex digit sequence

#TODO: need to handle this case where longest match would be incorrect: r'this is a raw string \' { expr } 'a separate string later'
@eat(String)
def eat_raw_string(src:str) -> int|None:
    """
    raw strings start with either r' or r", and are terminated by the matching quote delimiter
    raw strings may contain any character except the delimiter.
    Escapes and interpolations are ignored.
    The string ends at the first instance of the delimiter
    """
    if not src.startswith('r'):
        return None

    delim = src[1]
    if delim not in '"\'':
        return None

    i = 2
    while i < len(src) and src[i] != delim:
        i += 1

    if i == len(src):
        raise ValueError("unterminated raw string")

    return i + 1


#TODO: probably have separate eat function for eating a raw string?
#alternatively, could also just store the raw string with the parsed string... though if there were errors that would only work during raw parsing....need a separate eat func..

def tokenize(src:str, context:list[Context]|None=None) -> list[Token]:
    # if context is None:
    #     #top level tokenizing
    #     context = [Context.root]
    #     min_context = 0
    # else:
    #     #sub tokenizing. Stop when we try to do anything involving the parents context
    #     min_context = len(context)
    
    #get a list of all context free functions that are decorated with @eat
    eat_funcs = [func for _, func in get_eat_functions() if func._context_free]
    func_precedences = [precedence.get(func._token_cls, 0) for func in eat_funcs]

    tokens = []
    i = 0

    while i < len(src):
        #run all the eat functions on the current src
        matches = [eat_func(src[i:]) for eat_func in eat_funcs]

        #find the longest token that matched. if multiple tied for longest, use the one with the highest precedence.
        #raise an error if multiple tokens tied, and they have the same precedence
        key=lambda x: (x[0][0] or 0, x[1])
        matches = [*zip(matches, func_precedences)]
        best = max(matches, key=key)
        ties = [match for match in matches if key(match) == key(best)]
        if len(ties) > 1:
            raise ValueError(f"multiple tokens matches tied {[match[0][1].__name__ for match in ties]}: {repr(src[i:])}\nPlease disambiguate by providing precedence levels for these tokens.")

        (n_eaten, token_cls), _ = best


        #if we didn't match anything, raise an error
        if n_eaten is None:
            raise ValueError(f"failed to tokenize: ```{escape_whitespace(src[i:])}```.\nCurrent tokens: {tokens}")
        
        #add the token to the list of tokens (handling idempotent token cases)
        if not tokens or token_cls not in idempotent_tokens or not isinstance(tokens[-1], token_cls):
            tokens.append(token_cls(src[i:i+n_eaten]))

        #increment the index
        i += n_eaten

        #check if we need to stop tokenizing
        #TODO: this should go inside the loop?


    return tokens


def get_eat_functions() -> list[tuple[str, Callable[[str], tuple[int|None, Type[Token]]]]]:
    """Get a list of all functions decorated with @eat"""
    return [(name, func) for name, func in globals().items() if callable(func) and hasattr(func, "_is_eat_decorator") and func._is_eat_decorator]

def validate_functions():
    # Get all functions decorated with @eat(Token)
    decorated_functions = get_eat_functions()

    # Validate the function signatures
    for name, wrapper_func in decorated_functions:
        func = wrapper_func._eat_func
        signature = inspect.signature(func)
        param_types = [param.annotation for param in signature.parameters.values()]
        return_type = signature.return_annotation

        # Check if the function has the correct signature
        if len(param_types) != 1 or param_types[0] != str or return_type != int|None:
            raise ValueError(f"{func.__name__} has an invalid signature: `{signature}`. Expected `(src: str) -> int|None`")

    # check for any functions that start with eat_ but are not decorated with @eat
    decorated_func_names = {name for name, _ in decorated_functions}
    for name, func in globals().items():
        if name.startswith("eat_") and callable(func) and name not in decorated_func_names:
            raise ValueError(f"`{name}()` function is not decorated with @eat")


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


def test():
    """simple test dewy program"""

    with open('../../../examples/syntax.dewy') as f:
        src = f.read()

    tokens = tokenize(src)
    print(f'matched tokens: {tokens}')




if __name__ == "__main__":
    validate_functions()
    test()