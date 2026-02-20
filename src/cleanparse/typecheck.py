"""
semantic analysis pass 0: 
- type checking
- ambiguity resolution
"""

from . import t2
from . import p0

from .reporting import SrcFile, ReportException, Error, Pointer, Span
from dataclasses import dataclass
from collections import defaultdict
from typing import TypeAlias, Literal
from enum import Enum, auto

"""
Candidate type names:
Top: 
- any
Bottom:
- bottom
- never
- noreturn
- empty

I think noreturn will be a separate case from bottom
"""

TOP_TYPE: str = 'any'
BOTTOM_TYPE: str = 'never'  # don't use `never`, as we are separating control flow/effects from actual types
_named_types: set[str] = {TOP_TYPE, BOTTOM_TYPE} # void and inferred don't participate in type expressions
_type_parents: dict[str, set[str]] = defaultdict(set, {BOTTOM_TYPE: {TOP_TYPE}})
_type_children: dict[str, set[str]] = defaultdict(set, {TOP_TYPE: {BOTTOM_TYPE}})

def add_type(name: str, parent: str = TOP_TYPE) -> None:
    if name in _named_types:
        raise ValueError(f'Type {name} already defined')
    _named_types.add(name)
    # _type_parents[name].add(parent)
    # _type_children[parent].add(name)
    add_type_link(name, parent)

def add_type_link(child: str, parent: str) -> None:
    if child not in _named_types:
        raise ValueError(f'Type {child} not defined')
    if parent not in _named_types:
        raise ValueError(f'Type {parent} not defined')
    _type_parents[child].add(parent)
    _type_children[parent].add(child)

# TODO: want an arbitrary DAG renderer. should draw dags with unicode box drawing characters, no repeated nodes

# some types to add:
# insert basic types into the system
# note, things like partial order, comparable, etc. will be represented in the structural type system, not the type graph
system_types: list[str|tuple[str, str]] = [
    'undefined',
    'bool',
    'number',
    ('real', 'number'),
    ('rational', 'real'),
    ('int', 'rational'),
    ('uint', 'int'),
    ('uint8', 'uint'),
    ('uint16', 'uint'),
    ('uint32', 'uint'),
    ('uint64', 'uint'),
    ('uint128', 'uint'),
    ('int8', 'int'),
    ('int16', 'int'),
    ('int32', 'int'),
    ('int64', 'int'),

    # tbd string stuff
    'char',     # unicode scalar # rune # char # string<length=1>
    'grapheme', 
    'string',   # array<unicode_scalar> | array<grapheme>
    
    # container types
    'array',
    'dict',
    'set',
    'object',
]
for t in system_types:
    if isinstance(t, tuple): add_type(*t) 
    else: add_type(t)


@dataclass
class TypeAnd:
    items: list[TypeExpr]
    def __post_init__(self):
        assert len(self.items) > 1, f'TypeAnd must have at least two items, got {len(self.items)}'

@dataclass
class TypeOr:
    items: list[TypeExpr]
    def __post_init__(self):
        assert len(self.items) > 1, f'TypeOr must have at least two items, got {len(self.items)}'

@dataclass
class TypeNot:
    type: TypeExpr

Primitive: TypeAlias = str   # has to be in the _named_types set

# Special Types that don't participate in type expressions or the type hierarchy
VoidType: TypeAlias = Literal['void']
InferredType: TypeAlias = Literal['untyped']
NoReturnType: TypeAlias = Literal['noreturn']
VOID_TYPE: VoidType = 'void'
INFERRED_TYPE: InferredType = 'untyped'
NORETURN_TYPE: NoReturnType = 'noreturn'

TypeExpr: TypeAlias = Primitive | TypeAnd | TypeOr | TypeNot #| TypeParam | TKeyOf | TValueOf | TFieldOf | TContainer
Type: TypeAlias = TypeExpr | VoidType | InferredType | NoReturnType

@dataclass
class AST:
    span: Span
    type: Type # All ASTs have a type. typechecking involves propogating the type upward through expressions

# BinaryOperator: TypeAlias = Literal['']

# @dataclass
# class BinOp(AST):
#     op: BinaryOperator
#     left: AST
#     right: AST


def typecheck_and_resolve(srcfile: SrcFile) -> AST:
    block = p0.parse(srcfile)
    import pdb; pdb.set_trace()


def test():
    from ..myargparse import ArgumentParser
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    try:
        ast = typecheck_and_resolve(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    for ast in asts:
        print(p0.ast_to_tree_str(ast))
        # TODO: print the top level type of the AST
        print()
    
if __name__ == '__main__':
    test()