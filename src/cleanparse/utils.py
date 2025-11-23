from typing import Generator

def truncate(s:str, max_len:int=50) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


class classproperty:
    """
    Set properties on a class rather than instance

    Example:
    ```python
    class Foo:
        @classproperty
        def bar():
            return "bar"
    
    Foo.bar  # "bar"
    ```
    """
    def __init__(self, fget):
        self.fget = fget

    def __set_name__(self, owner, name):
        self.name = name  # optional, just for debugging

    def __get__(self, instance, owner=None):
        # Just call the function with no arguments
        return self.fget()


from typing import TypeVar
T = TypeVar('T')
def descendants(cls: type[T]) -> Generator[type[T], None, None]:
    for subclass in cls.__subclasses__():
        yield subclass
        yield from descendants(subclass)




def ordinalize(n: int) -> str:
    """
    Convert an integer into its ordinal numeral string.
    Examples: 1 -> '1st', 2 -> '2nd', 3 -> '3rd', 4 -> '4th', 11 -> '11th', etc.
    """
    prefix = ''
    if n < 0:
        prefix = '-'
        n *= -1

    # Special case for numbers ending in 11, 12, 13
    if 10 <= n % 100 <= 13:
        suffix = "th"
    else:
        last_digit = n % 10
        if last_digit == 1:
            suffix = "st"
        elif last_digit == 2:
            suffix = "nd"
        elif last_digit == 3:
            suffix = "rd"
        else:
            suffix = "th"

    return f"{prefix}{n}{suffix}"
