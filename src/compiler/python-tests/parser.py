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


class Token(ABC):
    def __repr__(self) -> str:
        """default repr for tokens is just the class name"""
        return f"<{self.__class__.__name__}>"

class WhiteSpace(Token):
    def __init__(self, _): ...

#token String
#   will contain body:list[str|list[Token]], i.e. the string chunks, and lists of tokens extracted from interpolations

# mark which tokens cannot be repeated in a list of tokens. E.g. whitespace should always be merged into a single token
idempotent_tokens = {
    WhiteSpace
}


def eat(cls:Type[Token]):
    """
    Decorator for functions that eat tokens. 
    Makes function return include constructor for token class that it tries to eat, in tupled with return.
    """
    assert issubclass(cls, Token), f"cls must be a subclass of Token, but got {cls}"
    def decorator(eat_func:Callable[[str], int|None]):
        def wrapper(src:str) -> tuple[int|None, Type[Token]]:
            return eat_func(src), cls
        wrapper._is_eat_decorator = True  # make it easy to check if a function has this decorator
        wrapper.eat_func = eat_func
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


def tokenize(src:str, context:list[Context]|None=None) -> list[Token]:
    if context is None:
        #top level tokenizing
        context = [Context.root]
        min_context = 0
    else:
        #sub tokenizing. Stop when we try to do anything involving the parents context
        min_context = len(context)
    
    #get a list of all functions that are decorated with @eat
    eat_funcs = [func for _, func in get_eat_functions()]

    tokens = []
    i = 0

    while i < len(src):
        #run all the eat functions on the current src
        matches = [eat_func(src[i:]) for eat_func in eat_funcs]

        #find the longest token that matched
        n_eaten, token_cls = max(matches, key=lambda x: x[0] if x[0] is not None else 0)

        #if we didn't match anything, raise an error
        if n_eaten is None:
            raise ValueError(f"failed to tokenize:\n{repr(src[i:])}.\nCurrent tokens: {tokens}")
        
        #add the token to the list of tokens (handling idempotent token cases)
        if not tokens or token_cls not in idempotent_tokens or not isinstance(tokens[-1], token_cls):
            tokens.append(token_cls(src[i:i+n_eaten]))

        #increment the index
        i += n_eaten


        # for eat_func in eat_funcs:
        #     num_eaten, token_cls = eat_func(src[i:])
        #     if num_eaten is not None:
        #         if token_cls not in idempotent_tokens or not tokens or not isinstance(tokens[-1], token_cls):
        #             tokens.append(token_cls(src[i:i+num_eaten]))
        #         i += num_eaten
        #         break
        # else:
        #     raise ValueError(f"failed to tokenize:\n{repr(src[i:])}.\nCurrent tokens: {tokens}")
        
        #check if we need to stop tokenizing
        #TODO: this should go inside the loop?



def get_eat_functions():
    """Get a list of all functions decorated with @eat"""
    return [(name, func) for name, func in globals().items() if callable(func) and hasattr(func, "_is_eat_decorator") and func._is_eat_decorator]

def validate_functions():
    # Get all functions decorated with @eat(Token)
    decorated_functions = get_eat_functions()
    print(decorated_functions)
    # Validate the function signatures
    for name, wrapper_func in decorated_functions:
        func = wrapper_func.eat_func
        signature = inspect.signature(func)
        param_types = [param.annotation for param in signature.parameters.values()]
        return_type = signature.return_annotation

        # Check if the function has the correct signature
        if len(param_types) != 1 or param_types[0] != str or return_type != int|None:
            raise ValueError(f"{func.__name__} has an invalid signature: `{signature}`. Expected `(src: str) -> int|None`")




def test():
    """simple test dewy program"""

    with open('../../../examples/syntax.dewy') as f:
        src = f.read()

    tokens = tokenize(src)
    pdb.set_trace()

    1




if __name__ == "__main__":
    validate_functions()
    test()