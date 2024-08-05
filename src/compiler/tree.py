from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Generator, Sequence


import pdb

"""
[Current work]
converting all ASTs into dataclasses
- methods operating on the AST nodes will be external, maybe implemented in dewy.py
"""

#TODO: make a nice generic tree maker helper class
# class TreeMaker:
#     """Helper class for generating tree representations of anything"""
#     def __init__(self, draw_branches=True):
#         self.space = '    '
#         if draw_branches: 
#             self.branch = '│   '
#             self.tee = '├── '
#             self.last = '└── '
#         else:
#             self.branch = self.space
#             self.tee = self.space
#             self.last = self.space
        
#         self.level = 0
#         self.prefix = ''

#     def reset(self):
#         self.level = 0
#         self.prefix = ''

#     def indent(self):
#         self.level += 1
    
#     def dedent(self):
#         if self.level == 0:
#             raise ValueError('Cannot dedent past root level')
#         self.level -= 1

#     def putline(self, line:str) -> str:



# Define a custom metaclass
class ASTMeta(ABCMeta):
    def __new__(cls, name, bases, dct):
        new_cls = super().__new__(cls, name, bases, dct)
        if ABC not in bases:
            # Apply the decorator if the base class is not ABC
            new_cls = dataclass(repr=False)(new_cls)
        return new_cls


@dataclass(repr=False)
class AST(metaclass=ASTMeta):
    # TODO: add property to all ASTs for function complete/locked/etc. meaning it and all children are settled
    @abstractmethod
    def __str__(self) -> str:
        """Return a string representation of the AST in a canonical dewy code format"""

    def __repr__(self) -> str:
        """
        Returns a string representation of the AST tree with correct indentation for each sub-component

        e.g. 
        SomeAST(prop0=..., prop1=...)
        ├── child0=SomeSubAST(...)
        ├── child1=SomeOtherAST(...)
        │   ├── a=ThisAST(...)
        │   └── b=ThatAST(...)
        └── child2=AST2(...)
            └── something=ThisLastAST(...)

        Where all non-ast attributes of a node are printed on the same line as the node itself
        and all children are recursively indented a level and printed on their own line
        """
        return '\n'.join(self._gentree())

    def _gentree(self, prefix:str='', name:str='') -> Generator[str, None, None]:
        """
        a recursive generator helper function for __repr__

        Args:
            prefix: str - the string to prepend to each child line (root line already has prefix)
            name: str - the name of the current node in the tree
            # draw_branches: bool - whether each item should be drawn with branches or only use whitespace
        
        Returns:
            str: the string representation of the AST tree
        """
        # prefix components:
        space = '    '
        branch = '│   '
        # pointers:
        tee = '├── '
        last = '└── '

        if name:
            name = f'{name}='
        attrs_str = ', '.join(f'{k}={v}' for k, v in self.__inners__() if not isinstance(v, AST))
        yield f'{name}{self.__class__.__name__}({attrs_str})'
        children = tuple((k, v) for k, v in self.__inners__() if isinstance(v, AST))
        pointers = [tee] * (len(children) - 1) + [last]
        for (k, v), pointer in zip(children, pointers):
            extension = branch if pointer == tee else space
            gen = v._gentree(f'{prefix}{extension}', name=k)
            yield f'{prefix}{pointer}{next(gen)}'
            yield from gen
    
    def __inners__(self) -> Generator[tuple[str, Any], None, None]:
        """A method for getting the __dict__.items() of the AST instance.
        Override if you want to adjust how the AST is represented in the tree
        e.g. a list might spread out its items into the dict items, etc.
        """
        yield from self.__dict__.items()


#DEBUG testing tree string printing
class Add(AST):
    l: AST
    r: AST
    def __str__(self) -> str:
        return f'{self.l} + {self.r}'


class Mul(AST):
    l: AST
    r: AST
    def __str__(self) -> str:
        return f'{self.l} * {self.r}'

class List(AST):
    items: list[AST]
    def __str__(self) -> str:
        return f'[{", ".join(map(str, self.items))}]'
    
    def __inners__(self) -> Generator[tuple[str, Any], None, None]:
        yield from (('', v) for v in self.items)
    

class Int(AST):
    value: int
    def __str__(self) -> str:
        return str(self.value)


# big long test ast
test = Add(
    Add(
        Int(1),
        List([Int(2), Int(3), Int(4), Int(5)])
    ),
    Mul(
        Int(2),
        Add(
            Mul(
                Int(3),
                Int(4)
            ),
            Mul(
                Int(5),
                Int(6)
            )
        )
    )
)      


print(repr(test))
pdb.set_trace()

class Type(AST):
    name: str
    parameters: list = field(default_factory=list)

    def __str__(self) -> str:
        if self.parameters:
            return f'{self.name}<{", ".join(map(str, self.parameters))}>'
        return self.name


class Undefined(AST):
    """undefined singleton"""

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Undefined, cls).__new__(cls)
        return cls.instance

    def __str__(self):
        return 'undefined'


class Void(AST):
    """void singleton"""

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Void, cls).__new__(cls)
        return cls.instance

    def __str__(self):
        return 'void'


class Identifier(AST):
    name: str

    def __str__(self) -> str:
        return f'{self.name}'


class TypedIdentifier(AST):
    id: Identifier
    type: Type

class DeclarationType(Enum):
    LET = auto()
    CONST = auto()
    LOCAL_CONST = auto()

    # default for binding without declaring
    DEFAULT = LET


class Declare(AST):
    decltype: DeclarationType
    target: Identifier | TypedIdentifier | UnpackTarget

    def __str__(self):
        return f'{self.decltype.name.lower()} {self.name}:{self.type}'


class Assign(AST):
    # TODO: allow bind to take in an unpack structure
    target: Declare | Identifier
    value: AST

    def __str__(self):
        return f'{self.target} = {self.value}'
