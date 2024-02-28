from typing import TypeVar, Generic
import pdb
from typing import Callable


def wrap_coords(method: Callable):
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


def fail_coords(method: Callable):
    def wrapped_method(self, *args, **kwargs):
        raise ValueError(f"coord_string_method {
                         method} cannot be called on a CoordString, as it will not return a CoordString")
    return wrapped_method


class CoordString(str):
    """
    Drop-in replacement for str that keeps track of the coordinates of each character in the string

    Identical to normal strings, but attaches the `row_col(i:int) -> tuple[int, int]` method
    which returns the (row, column) of the character at index i

    Args:
        anchor (tuple[int,int], optional): The row and column of the top left of the string. Defaults to (0, 0).
    """
    def __new__(cls, *args, anchor: tuple[int, int] = (0, 0), **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        row, col = anchor
        self.row_col_map = self._generate_row_col_map(row, col)

        return self

    # TODO: make init so that class recognized .row_col_map as property on instances
    # def __init__(self, s:str, row_col_map:list[tuple[int,int]]):

    def _generate_row_col_map(self, row=0, col=0) -> list[tuple[int, int]]:
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

    def loc(self, index):
        return self.row_col_map[index]

    @staticmethod
    def from_existing(new_str: str, old_coords: list[tuple[int, int]]) -> 'CoordString':
        new_coord_str = CoordString(new_str)
        new_coord_str.row_col_map = old_coords
        return new_coord_str

    # wrappers for string methods that should return CoordStrings
    def lstrip(self, *args, **kwargs):
        result = super().lstrip(*args, **kwargs)
        custom_str = CoordString(result)
        custom_str.row_col_map = self.row_col_map[len(self)-len(result):]
        return custom_str

    def rstrip(self, *args, **kwargs):
        result = super().rstrip(*args, **kwargs)
        custom_str = CoordString(result)
        custom_str.row_col_map = self.row_col_map[:len(result)]
        return custom_str

    def strip(self, *args, **kwargs):
        return self.lstrip(*args, **kwargs).rstrip(*args, **kwargs)

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

    @fail_coords
    def center(self, *args, **kwargs): ...

    @fail_coords
    def expandtabs(self, *args, **kwargs): ...

    @fail_coords
    def ljust(self, *args, **kwargs): ...

    @fail_coords
    def zfill(self, *args, **kwargs): ...


# TODO: maybe make adding this string with other regular str illegal


int_parsable_base_prefixes = {
    '0b': 2,  '0B': 2,
    '0t': 3,  '0T': 3,
    '0q': 4,  '0Q': 4,
    '0s': 6,  '0S': 6,
    '0o': 8,  '0O': 8,
    '0d': 10, '0D': 10,
    # '0z':12, #uses different digits Z/z and X/x (instead of A/a and B/b expected by int())
    '0x': 16, '0X': 16,
    '0u': 32, '0U': 32,
    '0r': 36, '0R': 36,
    # '0y':64, #more than int's max parsable base (36)
}


def based_number_to_int(src: str) -> int:
    """
    convert a number in a given base to an int
    """
    prefix, digits = src[:2], src[2:]
    if prefix in int_parsable_base_prefixes:
        return int(digits, int_parsable_base_prefixes[prefix])
    elif prefix == '0z':
        raise NotImplementedError(f"base {prefix} is not supported")
    elif prefix == '0y':
        raise NotImplementedError(f"base {prefix} is not supported")
    else:
        raise ValueError(f"INTERNAL ERROR: base {prefix} is not a valid base")


def bool_to_bool(src: str) -> bool:
    """
    convert a (case-insensitive) bool literal to a bool
    """
    try:
        return bool(['false', 'true'].index(src.lower()))
    except ValueError:
        raise ValueError(f"INTERNAL ERROR: bool {src} is not a valid bool") from None


class CaselessStr(str):
    def __init__(self, s: str):
        super().__init__()

    def __eq__(self, other: str):
        return self.casefold() == other.casefold()

    def __hash__(self):
        return hash(self.casefold())

    def __repr__(self):
        return f"(caseless)'{self.casefold()}'"

    def __str__(self):
        return self.casefold()


T = TypeVar('T')
U = TypeVar('U')


class CaseSelectiveDict(Generic[T]):
    """A dictionary where keys may be either case sensitive or case insensitive"""

    def __init__(self, **kwargs):
        self.caseless: dict[CaselessStr, any] = {}
        self.caseful: dict[str, any] = {}
        for k, v in kwargs.items():
            self.__setitem__(k, v)  # Use setitem to handle initial assignments

    def __getitem__(self, key: str | CaselessStr) -> T:
        try:
            return self.caseless[CaselessStr(key)]
        except KeyError:
            pass
        try:
            return self.caseful[key]
        except KeyError:
            pass

        raise KeyError(f"Key {key} not found") from None

    def __setitem__(self, key: str | CaselessStr, value: T):
        if not isinstance(key, (str, CaselessStr)):
            raise TypeError(f"Key must be of type str or CaselessStr, not '{type(key)}'")

        if CaselessStr(key) in self.caseless:
            if not isinstance(key, CaselessStr):
                key = CaselessStr(key)
            self.caseless[key] = value
            return

        if isinstance(key, CaselessStr):
            # need to check if the new key was in the caseful keys. This is an ERROR
            caseful_keys = [*self.caseful.keys()]
            folded_caseful_keys = [k.casefold() for k in caseful_keys]
            if key in folded_caseful_keys:
                existing_key = caseful_keys[folded_caseful_keys.index(key)]
                raise KeyError(f"Cannot insert key {repr(key)}. Caseful version {repr(existing_key)} already exists")
            self.caseless[key] = value
            return

        self.caseful[key] = value

    def __delitem__(self, key: str | CaselessStr):
        key = str(key)
        try:
            del self.caseless[CaselessStr(key)]
            return
        except KeyError:
            pass
        try:
            del self.caseful[key]
            return
        except KeyError:
            pass

        raise KeyError(f"Key {key} not found") from None

    def __contains__(self, key: str | CaselessStr):
        try:
            return CaselessStr(key) in self.caseless or key in self.caseful
        except TypeError:
            return False

    def has_key(self, key: str | CaselessStr):
        return key in self

    def get(self, key: str | CaselessStr, default: U = None) -> T | U:
        try:
            return self[key]
        except KeyError:
            return default

    def __len__(self):
        return len(self.caseless) + len(self.caseful)

    def __iter__(self):
        return iter(self.keys())

    def items(self):
        return {**self.caseless, **self.caseful}.items()

    def keys(self) -> list[str | CaselessStr]:
        return [*self.caseless.keys(), *self.caseful.keys()]

    def values(self) -> list[T]:
        return [*self.caseless.values(), *self.caseful.values()]

    def __repr__(self):
        return f"CaseSelectiveDict({self.caseless}, {self.caseful})"

    def __str__(self):
        items = {**self.caseless, **self.caseful}
        return f'{items}'
