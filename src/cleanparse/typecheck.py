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
VOID_TYPE: str = 'void'
# DYNAMIC_TYPE: str = 'untyped' # I think we might not support dynamic types. dynamic means the type is determined at runtime
INFERRED_TYPE: str = 'untyped'
_named_types: set[str] = {TOP_TYPE, BOTTOM_TYPE} # void and inferred don't participate in type expressions
_type_parents: dict[str, set[str]] = defaultdict(set, {BOTTOM_TYPE: [TOP_TYPE]})
_type_children: dict[str, set[str]] = defaultdict(set, {TOP_TYPE: [BOTTOM_TYPE]})

def add_type(name: str, parent: str = TOP_TYPE) -> None:
    if name in _named_types:
        raise ValueError(f'Type {name} already defined')
    _named_types.add(name)
    _type_parents[name].add(parent)
    _type_children[parent].add(name)

# TODO: want an arbitrary DAG renderer. should draw dags with unicode box drawing characters, no repeated nodes

# some types to add:
# insert basic types into the system
system_types: list[str|tuple[str, str]] = [
    'undefined',
    'string',
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

TypeExpr: TypeAlias = Primitive | TypeAnd | TypeOr | TypeNot #| TypeParam | TKeyOf | TValueOf | TFieldOf | TContainer
Type: TypeAlias = TypeExpr | Literal['void', 'untyped']

@dataclass
class AST:
    span: Span
    type: Type # All ASTs have a type. typechecking involves propogating the type upward through expressions



@dataclass
class BinOp(AST): ...

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
        asts, types = typecheck_and_resolve(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    for ast in asts:
        print(p0.ast_to_tree_str(ast))
        # TODO: print the top level type of the AST
        print()
    