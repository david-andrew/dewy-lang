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
from types import UnionType

import pdb

#### DEBUG rich traceback printing ####
from rich import traceback, print
traceback.install(show_locals=True)


# #TODO: tbd how this gets used
# #      context is useful to know which of the eat functions to use during tokenization
# #      e.g. when inside a string, only eat_character, eat_escape, and eat_block
# class Context(Enum):
#     root = auto()
#     block = auto()
#     # string = auto()
#     interpolation = auto()


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
    
# class Bind(Token):
#     def __init__(self, _): ...

class Block(Token):
    def __init__(self, body:list[Token], left:str, right:str):
        self.body = body
        self.left = left
        self.right = right
    def __repr__(self) -> str:
        body_str = ', '.join(repr(token) for token in self.body)
        return f"<Block: {self.left}{body_str}{self.right}>"

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
    
class Integer(Token):
    def __init__(self, src:str):
        self.src = src
    def __repr__(self) -> str:
        return f"<Integer: {self.src}>"

class Operator(Token):
    def __init__(self, op:str):
        self.op = op
    def __repr__(self) -> str:
        return f"<Operator: {self.op}>"
    
class Dot(Token):
    def __init__(self, _): ...

class DotDot(Token):
    def __init__(self, _): ...

# class DotDotDot(Token):
#     def __init__(self, _): ...

class Comma(Token):
    def __init__(self, _): ...


    


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

# delimiters for blocks, ranges TODO: <> may not be part of this... what are <> blocks?
pair_opening_delims = '{([<'
pair_closing_delims = '})]>'

#list of all operators sorted from longest to shortest
operators = sorted(
    ['+', '-', '*', '/', '%', '^', '@', 'not', 'and', 'or', 'nand', 'nor', 'xor', 'xnor', '<<', '>>', '<<<', '>>>', '<<<!', '!>>>', '=?', 'not?', '>?', '<?', '>=?', '<=?', 'in?', '<=>', ':>', '->', '<->', '<-', '=>', '@?', '=', ':=', '.', '..'], 
    key=len, 
    reverse=True
)


def peek_eat(cls:Type[Token], root:bool=True):
    """
    Decorator for functions that eat tokens, but only return how many characters would make up the token. 
    Makes function return include constructor for token class that it tries to eat, in tupled with return.
    """
    assert issubclass(cls, Token), f"cls must be a subclass of Token, but got {cls}"
    def decorator(eat_func:Callable[[str], int|None]):
        def wrapper(src:str) -> tuple[int|None, Type[Token]]:
            return eat_func(src), cls
        wrapper._is_peek_eat_decorator = True  # make it easy to check if a function has this decorator
        wrapper._eat_func = eat_func
        wrapper._token_cls = cls
        return wrapper
    return decorator

#TODO: full eat probably won't need to take the class as an argument, since the function will know how to construct the token itself
def full_eat(root:bool=True):
    def decorator(eat_func:Callable[[str], tuple[int, Token] | None]):
        """
        Decorator for functions that eat tokens, and return the token itself if successful.
        TBD what this actually does...for now, largely keep unmodified, but attach the metadata to the wrapped function
        """
        # pull cls it from the return type of eat_func (which should be a Union[tuple[int, Token], None])
        cls = inspect.signature(eat_func).return_annotation.__args__[0].__args__[1]
        def wrapper(*args, **kwargs):
            return eat_func(*args, **kwargs), cls
        wrapper._is_full_eat_decorator = True  # make it easy to check if a function has this decorator
        wrapper._eat_func = eat_func
        wrapper._token_cls = cls

        return wrapper
    return decorator


@peek_eat(WhiteSpace)
def eat_line_comment(src:str) -> int|None:
    """eat a line comment, return the number of characters eaten"""
    if src.startswith('//'):
        try:
            return src.index('\n') + 1
        except ValueError:
            return len(src)
    return None

@peek_eat(WhiteSpace)
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

@peek_eat(WhiteSpace)
def eat_whitespace(src:str) -> int|None:
    """Eat whitespace, return the number of characters eaten"""
    i = 0
    while i < len(src) and src[i].isspace():
        i += 1
    return i if i > 0 else None

@peek_eat(Keyword)
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


@peek_eat(Identifier)
def eat_identifier(src:str) -> int|None:
    """
    Eat an identifier, return the number of characters eaten
    
    identifiers are of the form  [a-zA-Z_] [0-9a-zA-Z_?!$&]*
    """
    i = 0
    while i < len(src) and src[i].isalnum() or src[i] in '_?!$&':
        i += 1
    return i if i > 0 else None



# @peek_eat(Bind)
# def eat_bind(src:str) -> int|None:
#     """eat a bind operator, return the number of characters eaten"""
#     if src.startswith('='):
#         return 1
#     return None


@peek_eat(Escape)
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
def eat_string(src:str) -> tuple[int, String] | None:
    """
    strings are delimited with either single (') or double quotes (")
    the character portion of a string may contain any character except the delimiter, \, or {.
    strings may be multiline
    strings may contain escape sequences of the form \s where s is either a known escape sequence or a single character
    strings may interpolation blocks which open with { and close with }

    Tokenizing of escape sequences and interpolation blocks is handled as sub-tokenization task via eat_block and eat_escape

    returns the number of characters eaten and an instance of the String token, containing the list of tokens/string chunks/escape sequences
    """
    if not src[0] in '"\'':
        return None
    
    delim = src[0]
    i = 1
    chunk_start = 1
    body = []

    #TODO: this doesn't add the string chunks...
    while i < len(src) and src[i] != delim:
        
        #regular characters
        if src[i] not in '\\{':
            i += 1
            continue

        #add the previous chunk before handling the escape/intepolation block
        if i > chunk_start:
            body.append(src[chunk_start:i])

        if src[i] == '\\':
            res, _ = eat_escape(src[i:])
            if res is None:
                raise ValueError("invalid escape sequence")
            body.append(Escape(src[i:i+res]))
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
    
    return i + 1, String(body)

#random note: if you for some reason needed to do a unicode escape followed by a character that happens to be a hex digit, you could do \u##{}#, where the empty block {} breaks the hex digit sequence


@peek_eat(String)
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


@peek_eat(Integer)
def eat_integer(src:str) -> int|None:
    """
    eat an integer, return the number of characters eaten
    integers are of the form [0-9]+
    """
    i = 0
    while i < len(src) and src[i].isdigit():
        i += 1
    return i if i > 0 else None

@peek_eat(Operator)
def eat_operator(src:str) -> int|None:
    """
    eat a unary or binary operator, return the number of characters eaten
    unary operators: + - @ not TODO: others?
    binary operators: 
        + - * / % ^ 
        and or nand nor xor xnor 
        << >> >>> <<< <<<! !>>>
        =? not? >? <? >=? <=? in?
        <=>
        :>
        -> <-> <-
        =>
        @?
        = :=
        . ..

    picks the longest matching operator
    """
    for op in operators:
        if src.startswith(op):
            return len(op)
    return None


@peek_eat(Comma)
def eat_comma(src:str) -> int|None:
    """
    eat a comma, return the number of characters eaten
    """
    return 1 if src.startswith(',') else None



class EatTracker:
    i: int
    tokens: list[Token]

@full_eat()
def eat_block(src:str, tracker:EatTracker|None=None) -> tuple[int, Block] | None:
    """
    Eat a block, return the number of characters eaten and an instance of the Block token

    blocks are { ... } or ( ... ) and may contain sequences of any other tokens including other blocks

    if return_partial is True, then returns (i, body) in the case where the eat process fails, instead of None
    """
    
    if not src or src[0] not in pair_opening_delims:
        return None
    
    # save the opening delimiter
    left = src[0]
    
    # try:
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
        matches = [eat_func(src[i:]) for eat_func in root_eat_funcs]

        #find the longest token that matched. if multiple tied for longest, use the one with the highest precedence.
        #raise an error if multiple tokens tied, and they have the same precedence
        def key(x):
            (res, _cls), precedence = x
            if res is None:
                return 0, precedence
            if isinstance(res, tuple):
                res, _token = res #full_eat functions return a tuple of (num_chars_eaten, token)
            return res, precedence

        matches = [*zip(matches, root_func_precedences)]
        best = max(matches, key=key)
        ties = [match for match in matches if key(match) == key(best)]
        if len(ties) > 1:
            raise ValueError(f"multiple tokens matches tied {[match[0][1].__name__ for match in ties]}: {repr(src[i:])}\nPlease disambiguate by providing precedence levels for these tokens.")

        (res, token_cls), _ = best

        #if we didn't match anything, return None
        if res is None:
            return None
        
        if isinstance(res, tuple):
            n_eaten, token = res
            body.append(token)
        else:
            #add the token to the list of tokens (handling idempotent token cases)
            n_eaten = res
            if not body or token_cls not in idempotent_tokens or not isinstance(body[-1], token_cls):
                body.append(token_cls(src[i:i+n_eaten]))

        #increment the index
        i += n_eaten
        if tracker:
            tracker.i = i

    if i == len(src):
        raise ValueError("unterminated block")
    
    # closing delim (doesn't need to match opening delim)
    right = src[i]
    assert left in pair_opening_delims and right in pair_closing_delims, f"invalid block delimiters: {left} {right}"

    #include closing delimiter in character count
    i += 1
    if tracker:
        tracker.i = i

    return i, Block(body, left=left, right=right)



    
    #TODO: need to separate out the full_eat and peek_eat functions
    #      probably if any full eat functions return, they take precedence over the peek eat functions
    #TODO: TBD if should include _token_cls on full_eat functions... ideally we'd pull it from the signature since they should say what type of token they return



#TODO: perhaps root_eat could be a property added by the decorator
root_eat_funcs = [
    eat_line_comment,
    eat_block_comment,
    eat_whitespace,
    eat_keyword,
    eat_identifier,
    eat_string,
    eat_raw_string,
    eat_integer,
    eat_operator,
    eat_comma,
    eat_block
]
root_func_precedences = [precedence.get(func._token_cls, 0) for func in root_eat_funcs]



def tokenize(src:str) -> list[Token]:

    # insert src into a block
    src = f'{{\n{src}\n}}'

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

    


def validate_functions():

    # Validate the @peek_eat function signatures
    peek_eat_functions = [(name, func) for name, func in globals().items() if callable(func) and getattr(func, '_is_peek_eat_decorator', False)]
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
    full_eat_functions = [(name, func) for name, func in globals().items() if callable(func) and getattr(func, '_is_full_eat_decorator', False)]
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


def test():
    """simple test dewy program"""

    with open('../../../examples/syntax.dewy') as f:
        src = f.read()

    tokens = tokenize(src)
    print(f'matched tokens:')
    for t in tokens:
        print(f'  {t}')




if __name__ == "__main__":
    validate_functions()
    test()