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
from typing import Callable, Any, Type

import pdb


class Context(Enum):
    root = auto()
    string = auto()
    interpolation = auto()


class Token(ABC): ...
class WhiteSpace(Token):
    def __init__(self, _): ...





def eat(cls:Type[Token]):
    """
    Decorator for functions that eat tokens. 
    Makes function return include constructor for token class that it tries to eat, in tupled with return.
    """
    assert issubclass(cls, Token), f"cls must be a subclass of Token, but got {cls}"
    def decorator(eat_fn:Callable[[str], int|None]):
        def wrapper(src:str) -> tuple[int|None, Type[Token]]:
            return eat_fn(src), cls
        wrapper._is_eat_decorator = True  # make it easy to check if a function has this decorator
        wrapper.eat_fn = eat_fn
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




#TODO: maybe some use of sub-parsing where a sub-string is given, possibly not entirely parsed, and then the tokens is returned + the remaining string
#      need to tell sub parser when to stop though, by passing some sort of closing token it's looking for, e.g. }, but at that point, why not just do everything with the context stack?
def tokenize(src:str) -> list[Token]:
    #get a list of all functions that are decorated with @eat
    eat_funcs = get_eat_functions()
    
    context = [Context.root]
    ...





def test():
    """simple test dewy program"""

    with open('../../../examples/syntax.dewy') as f:
        src = f.read()

    tokens = tokenize(src)
    pdb.set_trace()

    1

def get_eat_functions():
    """Get a list of all functions decorated with @eat"""
    return [(name, func) for name, func in globals().items() if callable(func) and hasattr(func, "_is_eat_decorator") and func._is_eat_decorator]

def validate_functions():
    # Get all functions decorated with @eat(Token)
    decorated_functions = get_eat_functions()
    print(decorated_functions)
    # Validate the function signatures
    for name, wrapper_func in decorated_functions:
        func = wrapper_func.eat_fn
        signature = inspect.signature(func)
        param_types = [param.annotation for param in signature.parameters.values()]
        return_type = signature.return_annotation

        # Check if the function has the correct signature
        if len(param_types) != 1 or param_types[0] != str or return_type != int|None:
            raise ValueError(f"{func.__name__} has an invalid signature: `{signature}`. Expected `(src: str) -> int|None`")


validate_functions()


if __name__ == "__main__":
    test()