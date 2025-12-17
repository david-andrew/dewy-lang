from typing import Generator, Any

def first_line(s:str) -> str:
    return s.split('\n')[0]

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


def index_of(item: Any, items: list) -> int|None:
    """determine the index of the item in the list, or None if not found. Matches on Identity (i.e. `A is B`)"""
    return next((i for i, t in enumerate(items) if t is item), None)


# from dataclasses import dataclass
# from collections.abc import MutableSequence

# @dataclass
# class ListView(MutableSequence):
#     data: list
#     start: int = 0
#     stop: int | None = None

#     def __post_init__(self):
#         if self.stop is None:
#             self.stop = len(self.data)
#         # basic normalization (supports negative indices)
#         n = len(self.data)
#         if self.start < 0:
#             self.start += n
#         if self.stop < 0:
#             self.stop += n

#     def __len__(self):
#         return max(0, self.stop - self.start)

#     def _check_index(self, i: int) -> int:
#         if i < 0:
#             i += len(self)
#         if not (0 <= i < len(self)):
#             raise IndexError(i)
#         return self.start + i

#     def __getitem__(self, i):
#         if isinstance(i, slice):
#             # return another view (still referencing same backing list)
#             start, stop, step = i.indices(len(self))
#             if step != 1:
#                 raise ValueError("step != 1 not supported in this simple view")
#             return ListView(self.data, self.start + start, self.start + stop)
#         return self.data[self._check_index(i)]

#     def __setitem__(self, i, value):
#         self.data[self._check_index(i)] = value

#     def __delitem__(self, i):
#         del self.data[self._check_index(i)]
#         self.stop -= 1  # keep view end aligned with backing changes

#     def insert(self, i, value):
#         # insert into backing list within view bounds
#         if i < 0:
#             i += len(self)
#         i = max(0, min(i, len(self)))
#         self.data.insert(self.start + i, value)
#         self.stop += 1



# from collections.abc import MutableSequence

# class ListView(MutableSequence):
#     def __init__(self, data, start=0, stop=None):
#         self.data = data
#         self.start = start
#         self.stop = len(data) if stop is None else stop
#         self._normalize()

#     def _normalize(self):
#         n = len(self.data)
#         if self.start < 0:
#             self.start += n
#         if self.stop < 0:
#             self.stop += n
#         self.start = max(0, self.start)
#         self.stop = min(n, self.stop)

#     def __len__(self):
#         return max(0, self.stop - self.start)

#     def _check_index(self, i):
#         if i < 0:
#             i += len(self)
#         if not 0 <= i < len(self):
#             raise IndexError(i)
#         return self.start + i

#     def __getitem__(self, i):
#         if isinstance(i, slice):
#             start, stop, step = i.indices(len(self))
#             if step != 1:
#                 raise ValueError("slice steps other than 1 not supported")
#             return ListView(self.data,
#                             self.start + start,
#                             self.start + stop)
#         return self.data[self._check_index(i)]

#     def __setitem__(self, i, value):
#         self.data[self._check_index(i)] = value

#     def __delitem__(self, i):
#         del self.data[self._check_index(i)]
#         self.stop -= 1

#     def insert(self, i, value):
#         if i < 0:
#             i += len(self)
#         i = max(0, min(i, len(self)))
#         self.data.insert(self.start + i, value)
#         self.stop += 1
