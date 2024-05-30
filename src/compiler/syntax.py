from abc import ABC, abstractmethod
from typing import Generator

from tokenizer import escape_whitespace  # TODO: move into utils

import pdb


class AST(ABC):
    @abstractmethod
    def treestr(self, prefix='') -> str:
        """Return a string representation of the AST tree"""
    @abstractmethod
    def __str__(self) -> str:
        """Return a string representation of the AST as dewy code"""
    @abstractmethod
    def __repr__(self) -> str:
        """Return a string representation of the python objects making up the AST"""

    def __iter__(self) -> Generator['AST', None, None]:
        """Return a generator of the children of the AST"""
        return  # default, no children

    def is_settled(self) -> bool:
        """Return True if the neither the AST, nor any of its children, are prototypes"""
        for child in self:
            if not child.is_settled():
                return False
        return True


class PrototypeAST(AST, ABC):
    """Used to represent AST nodes that are not complete, and must be removed before the whole AST is evaluated"""

    def is_settled(self) -> bool:
        """By definition, prototypes are not settled"""
        return False


class Undefined(AST):
    """undefined singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Undefined, cls).__new__(cls)
        return cls.instance

    def treestr(self, prefix='') -> str:
        return prefix + 'Undefined'

    def __str__(self) -> str:
        return 'undefined'

    def __repr__(self) -> str:
        return 'Undefined()'


# undefined shorthand, for convenience
undefined = Undefined()


class Void(AST):
    """void singleton"""
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Void, cls).__new__(cls)
        return cls.instance

    def treestr(self, prefix='') -> str:
        return prefix + 'Void'

    def __str__(self) -> str:
        return 'void'

    def __repr__(self) -> str:
        return 'Void()'


# void shorthand, for convenience
void = Void()


class Identifier(AST):
    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return f'{self.name}'

    def __repr__(self) -> str:
        return f'Identifier({self.name})'

    def treestr(self, prefix='') -> str:
        return prefix + f'Identifier: {self.name}'


class ListOfASTs(PrototypeAST):
    """Intermediate step for holding a list of ASTs that are probably captured by a container"""

    def __init__(self, asts: list[AST]):
        self.asts = asts

    def __str__(self):
        return f'{", ".join(map(str, self.asts))}'

    def __repr__(self):
        return f'ListOfASTs({self.asts})'

    def treestr(self, prefix='') -> str:
        pdb.set_trace()
        raise NotImplementedError('ListOfASTs.treestr')

    def __iter__(self) -> Generator[AST, None, None]:
        yield from self.asts


class String(AST):
    def __init__(self, val: str):
        self.val = val

    def __str__(self) -> str:
        return f'"{escape_whitespace(self.val)}"'

    def __repr__(self):
        return f'String({repr(self.val)})'

    def treestr(self, indent=0):
        pdb.set_trace()
        return f'{tab * indent}String: `{self.val}`'


class IString(AST):
    def __init__(self, parts: list[AST]):
        self.parts = parts

    def treestr(self, indent=0):
        pdb.set_trace()
        s = tab * indent + 'IString\n'
        for part in self.parts:
            s += part.treestr(indent + 1) + '\n'
        return s

    def __str__(self):
        s = ''
        for part in self.parts:
            if isinstance(part, String):
                s += part.val
            else:
                s += f'{{{part}}}'
        return f'"{s}"'

    def __repr__(self):
        return f'IString({repr(self.parts)})'

    def __iter__(self) -> Generator[AST, None, None]:
        yield from self.parts


# class FunctionLiteral(AST):
#     def __init__(self, args: list[Declare], kwargs: list[Bind], body: AST):
#         self.args = args
#         self.kwargs = kwargs
#         self.body = body

#     def eval(self, scope: Scope) -> 'Function':
#         return Function(self.args, self.kwargs, self.body, scope)
