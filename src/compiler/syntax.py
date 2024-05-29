from abc import ABC, abstractmethod
from typing import Generator

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

    @abstractmethod
    def children(self) -> Generator['AST', None, None]:
        """Return a generator of the children of the AST"""

    def is_settled(self) -> bool:
        """Return True if the neither the AST, nor any of its children, are prototypes"""
        for child in self.children():
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

    def children(self) -> Generator[AST, None, None]:
        return


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

    def children(self) -> Generator[AST, None, None]:
        return


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

    def children(self) -> Generator[AST, None, None]:
        return


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

    def children(self) -> Generator[AST, None, None]:
        for ast in self.asts:
            yield ast
