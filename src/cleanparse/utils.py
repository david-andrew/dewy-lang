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