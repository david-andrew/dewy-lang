from dataclasses import dataclass
from collections import defaultdict
from typing import TypeAlias, Literal

import pdb

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

# TODO: probably convert most of this into a class so that you just make a fresh instance when type checking a program
# rather than assuming that we will only type-check a single program


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


@dataclass
class TypeFunc:
    args: list[TypeExpr]
    ret: TypeExpr

Primitive: TypeAlias = str   # has to be in the _named_types set

# Special Types that don't participate in type expressions or the type hierarchy
VoidType: TypeAlias = Literal['void']
InferredType: TypeAlias = Literal['untyped']
NoReturnType: TypeAlias = Literal['noreturn']
VOID_TYPE: VoidType = 'void'
INFERRED_TYPE: InferredType = 'untyped'
NORETURN_TYPE: NoReturnType = 'noreturn'

TypeExpr: TypeAlias = Primitive | TypeAnd | TypeOr | TypeNot | TypeFunc #| TypeParam | TKeyOf | TValueOf | TFieldOf | TContainer
Type: TypeAlias = TypeExpr | VoidType | InferredType | NoReturnType # probably won't ever have a dynamic type, but if we did, it would also go here


# TODO: type algebra/operations functions

def is_subtype(t: Primitive, target: Primitive) -> bool:
    """Check if `t` is a subtype of `target`"""
    if t == target: return True
    frontier = [t]
    while frontier:
        current = frontier.pop()
        if current == target: return True
        frontier.extend(_type_parents[current])
    return False
    

def satisfies(t: TypeExpr, target: TypeExpr) -> bool:
    """Check if `t` satisfies the `target` type expression"""
    # TODO: t at the moment basically has to be primitive. but can't certain type expressions of t match certain targets?
    if not isinstance(t, Primitive): print(f'DEBUG WARNING: in `satisfies`, encountered `t` that is not a primitive type. {t=}')

    if isinstance(target, Primitive):
        if not isinstance(t, Primitive): return False
        return is_subtype(t, target)
    if isinstance(target, TypeOr):
        return any(satisfies(t, item) for item in target.items)
    if isinstance(target, TypeAnd):
        return all(satisfies(t, item) for item in target.items)
    if isinstance(target, TypeNot):
        return not satisfies(t, target.type)
    if isinstance(target, TypeFunc):
        if isinstance(t, TypeFunc):
            return all(satisfies(t_arg, target_arg) for t_arg, target_arg in zip(t.args, target.args)) and satisfies(t.ret, target.ret)
        return False

    pdb.set_trace()
    # should be unreachable, but indicates unhandled case
    return False

# TODO: come up with canonical names for each operator (e.g. division/mod)
system_binops: list[tuple[str, TypeExpr, TypeExpr]] = [
    ('__add__', 'number', 'number'),      #TODO: type here should be anything that is ring or group or ...
    ('__sub__', 'number', 'number'),
    ('__mul__', 'number', 'number'),
    ('__idiv__', 'number', 'number'),
    ('__mod__', 'number', 'number'),
    ('__tdiv__', 'number', 'number'),
    ('__pow__', 'number', 'number'),
   
    # Don't worry about these for now...    
    # ('__lshift__', 'int', 'int'),
    # ('__rshift__', 'int', 'int'),
    # ('__lrotate__', 'int', 'int'),
    # ('__rrotate__', 'int', 'int'),
    
    # ('__eq__', 'any', 'any'),
    # ('__neq__', 'any', 'any'),
    # # ('__gt__', 'comparable', 'comparable'),   #TODO: type here is anything that is partial orderable... but also have to be comparable to its own type...
    # # ('__lt__', 'comparable', 'comparable'),   #      basically what would our notation for traits on generic types be?   <T>   T<traits=comparable>
    # # ('__gte__', 'comparable', 'comparable'),
    # # ('__lte__', 'comparable', 'comparable'),   __gt__ = <T has PartialOrder>(left:T right:T):>bool => ...

    # ('__is__', 'any', 'type'),
    # ('__isnt__', 'any', 'type'),


    # TODO: what about iterators  e.g. `x in X and y in Y`
    ('__and__', 'bool', 'bool'),
    ('__or__', 'bool', 'bool'),
    ('__nand__', 'bool', 'bool'),
    ('__nor__', 'bool', 'bool'),
    ('__xor__', 'bool', 'bool'),
    ('__xnor__', 'bool', 'bool'),
]


# system_prefixops: list[tuple[str, TypeExpr]] = []
# system_postfixops: list[tuple[str, TypeExpr]] = []