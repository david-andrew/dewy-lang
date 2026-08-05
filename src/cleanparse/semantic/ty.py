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
Dynamic:
- <dewy probably just won't support dynamic/runtime types>
- dyn

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
_system_types: list[str|tuple[str, str]] = [
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
    'char', #'uscalar',     # char # unicode scalar # rune # char # string<length=1>. Not a 'codepoint'
    'grapheme', 
    'string',   # array<unicode_scalar> | array<grapheme>
    
    # container types
    'array',
    'dict',
    'set',
    'object',

    # tbd misc stuff
    'ID' # a generic thing representing some way to identify something. implementations may use specific data types like int, string, etc., but conceptually an ID is basically it's own separate thing
]
for t in _system_types:
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
class TypeParam:
    t: TypeExpr
    args: list[TypeExpr] #TODO: other stuff can be set here, though perhaps it doesn't affect the typing?

# @dataclass
# class TypeFunc:
#     args: list[TypeExpr]
#     ret: TypeExpr

Primitive: TypeAlias = str   # has to be in the _named_types set

# Special Types that don't participate in type expressions or the type hierarchy
VoidType: TypeAlias = Literal['void']
InferredType: TypeAlias = Literal['untyped']
NoReturnType: TypeAlias = Literal['noreturn']
VOID_TYPE: VoidType = 'void'
INFERRED_TYPE: InferredType = 'untyped'
NORETURN_TYPE: NoReturnType = 'noreturn'

TypeExpr: TypeAlias = Primitive | TypeAnd | TypeOr | TypeNot | TypeParam #| TypeFunc | TypeParam | TKeyOf | TValueOf | TFieldOf | TContainer
Type: TypeAlias = TypeExpr | VoidType | InferredType | NoReturnType # probably won't ever have a dynamic type, but if we did, it would also go here


# Type algebra is driven by: is_subtype(t, target) => is_empty(t & ~target) for arbitrary type expressions t and target.

# TODO: type algebra/operations functions
# probably merge is_subtype and satisfies. Or make is_subtype a pure nominal subtype lookup
# `A of? B | C` => `(A of? B) or (A of? C)`
# `A of! B & C` => `(A of! B) and (A of! C)`
# `A of? not B` => `not (A of? B)`
# `A<B> of? C<D>` => `(A of? C) and (B of? D)`
# `A<B> of? C` => `A of? C`
# `A of? C<D>` => `(A of? C) and (T of? D)` (where any is the largest type that can parameterize `A`). I think typically this one will be false, so probably just short circuit for now
# `(A | B) of? C` => `(A of? C) and (B of? C)`
# `(A & B) of? C` => `(A of? C) or (B of? C)`  This one is a little weird. should it be `or`` or `and``


# A | B of? C | D => A of? (C | D) and B of? (C | D) => ((A of? C) or (A of? D)) and ((B of? C) or (B of? D))


#######################################################################
# Semantic Subtyping
# is_subtype(S, T)  ⟺  is_empty(S & ~T)
# TypeParam is covariant in all args.
#######################################################################


LiteralAtom: TypeAlias = Primitive | TypeParam
# (is_positive, atom)
DnfClause: TypeAlias = tuple[tuple[bool, LiteralAtom], ...]
Dnf: TypeAlias = tuple[DnfClause, ...]  # () == never; ((),) == any (one empty clause)


# ---------------------------------------------------------------------------
# Smart constructors
# ---------------------------------------------------------------------------

def intersect(*xs: TypeExpr) -> TypeExpr:
    """Build the intersection of type expressions.

    Flattens nested TypeAnd nodes and absorbs identities/annihilators:
    - `any` is dropped (T & any = T)
    - `never` short-circuits to `never` (T & never = never)
    - no conjuncts left → `any`; a single conjunct → that type alone
    """
    flat: list[TypeExpr] = []
    for x in xs:
        if x == TOP_TYPE:
            continue
        if x == BOTTOM_TYPE:
            return BOTTOM_TYPE
        if isinstance(x, TypeAnd):
            flat.extend(x.items)
        else:
            flat.append(x)
    if not flat:
        return TOP_TYPE
    if len(flat) == 1:
        return flat[0]
    return TypeAnd(tuple(flat))


def union(*xs: TypeExpr) -> TypeExpr:
    """Build the union of type expressions.

    Flattens nested TypeOr nodes and absorbs identities/annihilators:
    - `never` is dropped (T | never = T)
    - `any` short-circuits to `any` (T | any = any)
    - no disjuncts left → `never`; a single disjunct → that type alone
    """
    flat: list[TypeExpr] = []
    for x in xs:
        if x == BOTTOM_TYPE:
            continue
        if x == TOP_TYPE:
            return TOP_TYPE
        if isinstance(x, TypeOr):
            flat.extend(x.items)
        else:
            flat.append(x)
    if not flat:
        return BOTTOM_TYPE
    if len(flat) == 1:
        return flat[0]
    return TypeOr(tuple(flat))


# ---------------------------------------------------------------------------
# Negation → NNF (Not only on atoms)
# ---------------------------------------------------------------------------

def negate(t: TypeExpr) -> TypeExpr:
    if t == TOP_TYPE:
        return BOTTOM_TYPE
    if t == BOTTOM_TYPE:
        return TOP_TYPE
    if isinstance(t, TypeNot):
        return to_nnf(t.type)
    if isinstance(t, TypeOr):
        return intersect(*(negate(x) for x in t.items))
    if isinstance(t, TypeAnd):
        return union(*(negate(x) for x in t.items))
    # Primitive | TypeParam: keep as Not(atom). Do NOT push not into TypeParam args.
    return TypeNot(t)


def to_nnf(t: TypeExpr) -> TypeExpr:
    if isinstance(t, TypeNot):
        return negate(t.type)
    if isinstance(t, TypeOr):
        return union(*(to_nnf(x) for x in t.items))
    if isinstance(t, TypeAnd):
        return intersect(*(to_nnf(x) for x in t.items))
    if isinstance(t, TypeParam):
        return TypeParam(to_nnf(t.t), tuple(to_nnf(a) for a in t.args))
    return t  # Primitive | top | bottom


# ---------------------------------------------------------------------------
# Normalize → DNF of signed atoms
# ---------------------------------------------------------------------------

def normalize(t: TypeExpr) -> Dnf:
    return _dnf(to_nnf(t))


def _dnf(t: TypeExpr) -> Dnf:
    if t == BOTTOM_TYPE:
        return ()
    if t == TOP_TYPE:
        return ((),)  # true
    if isinstance(t, TypeNot):
        # NNF: inner is atom
        return (((False, t.type),),)
    if isinstance(t, (str, TypeParam)):
        return (((True, t),),)
    if isinstance(t, TypeOr):
        clauses: list[DnfClause] = []
        for x in t.items:
            clauses.extend(_dnf(x))
        return tuple(clauses)
    if isinstance(t, TypeAnd):
        acc: Dnf = ((),)
        for x in t.items:
            acc = _distribute(acc, _dnf(x))
        return acc
    raise TypeError(f'normalize: unhandled {t!r}')


def _distribute(left: Dnf, right: Dnf) -> Dnf:
    if not left or not right:
        return ()
    out: list[DnfClause] = []
    for a in left:
        for b in right:
            out.append(a + b)
    return tuple(out)


# ---------------------------------------------------------------------------
# Nominal atom theory
# ---------------------------------------------------------------------------

def _is_nom_subtype(a: Primitive, b: Primitive) -> bool:
    if a == b:
        return True
    frontier = [a]
    seen = {a}
    while frontier:
        cur = frontier.pop()
        for parent in _type_parents[cur]:
            if parent == b:
                return True
            if parent not in seen:
                seen.add(parent)
                frontier.append(parent)
    return False


def _meet_prim(a: Primitive, b: Primitive) -> Primitive | None:
    """GLB for tree-ish nominal DAG. None => disjoint / uninhabited."""
    if _is_nom_subtype(a, b):
        return a
    if _is_nom_subtype(b, a):
        return b
    return None  # unrelated => empty (v1)


# ---------------------------------------------------------------------------
# Constructor heads + covariant TypeParam
# ---------------------------------------------------------------------------

def _head_of(atom: LiteralAtom) -> TypeExpr:
    return atom.t if isinstance(atom, TypeParam) else atom


def _args_of(atom: LiteralAtom) -> tuple[TypeExpr, ...]:
    return atom.args if isinstance(atom, TypeParam) else ()


def _as_prim_head(head: TypeExpr) -> Primitive | None:
    """v1: constructor heads are primitives (array, dict, …)."""
    return head if isinstance(head, str) else None


def _meet_atoms(a: LiteralAtom, b: LiteralAtom) -> LiteralAtom | None:
    """
    Positive meet of two atoms.
    Covariant TypeParam:
      F<A> & G<B>  (F of? G)  =>  F<A & B>
      F<A> & G<B>  (G of? F)  =>  G<A & B>
      unrelated heads          =>  None (empty)
    Bare prim meets param by treating bare as head with no arg constraint
      array & array<int> => array<int>   if heads meet to array
    """
    ha, hb = _head_of(a), _head_of(b)
    pa, pb = _as_prim_head(ha), _as_prim_head(hb)
    if pa is None or pb is None:
        # v1: non-primitive heads unsupported / only equal opaque heads
        if ha == hb and _args_of(a) == _args_of(b):
            return a
        return None

    head_meet = _meet_prim(pa, pb)
    if head_meet is None:
        return None

    args_a, args_b = _args_of(a), _args_of(b)
    if not args_a and not args_b:
        return head_meet
    if not args_a:
        # bare F & G<B...> => head_meet<B...>  (e.g. collection & array<int> => array<int>)
        return TypeParam(head_meet, args_b)
    if not args_b:
        return TypeParam(head_meet, args_a)

    if len(args_a) != len(args_b):
        return None  # arity mismatch => empty

    # covariant: intersect args pointwise
    meet_args = tuple(intersect(x, y) for x, y in zip(args_a, args_b))
    # if any arg intersect is never, whole param is never
    if any(is_empty(arg) for arg in meet_args):
        # array<never> — treat as empty type in v1 (no values)
        return None
    return TypeParam(head_meet, meet_args)


def _atom_implies_atom(a: LiteralAtom, b: LiteralAtom) -> bool:
    """
    Positive atom a is subtype of positive atom b.
    Covariant:
      F<A...> of? G<B...>  ⟺  (F of? G) and all (Ai of? Bi)
      F<A...> of? G        ⟺  F of? G
      F of? G<B...>        ⟺  false   (open world; can't invent args)
    """
    ha, hb = _head_of(a), _head_of(b)
    pa, pb = _as_prim_head(ha), _as_prim_head(hb)
    args_a, args_b = _args_of(a), _args_of(b)

    if pa is None or pb is None:
        return a == b

    if not _is_nom_subtype(pa, pb):
        return False

    if not args_b:
        # F<A> of? G  or  F of? G
        return True
    if not args_a:
        # F of? G<B> — open world
        return False
    if len(args_a) != len(args_b):
        return False

    # covariance
    return all(is_subtype(ai, bi) for ai, bi in zip(args_a, args_b))


# ---------------------------------------------------------------------------
# Clause emptiness
# ---------------------------------------------------------------------------

def clause_is_empty(clause: DnfClause) -> bool:
    """
    Clause = P1 & P2 & … & ~N1 & ~N2 & …
    Empty iff the positive meet is uninhabited, or it is implied by some ~Ni
    (i.e. meet of? Ni).
    """
    pos = [atom for pol, atom in clause if pol]
    neg = [atom for pol, atom in clause if not pol]

    # reduce positives by successive meet
    meet: LiteralAtom | None
    if not pos:
        meet = TOP_TYPE  # only negatives: ~N1 & ~N2 & … usually non-empty
    else:
        meet = pos[0]
        for atom in pos[1:]:
            meet = _meet_atoms(meet, atom)
            if meet is None:
                return True

    if meet == BOTTOM_TYPE:
        return True

    # top with only negatives → non-empty (open world)
    if meet == TOP_TYPE:
        return False

    # P & ~N empty iff P of? N
    for n in neg:
        if _atom_implies_atom(meet, n):
            return True

    return False


def is_empty(t: TypeExpr) -> bool:
    """True iff t is uninhabited."""
    dnf = normalize(t)
    # prune as we go; all clauses empty => empty type
    return all(clause_is_empty(c) for c in dnf)


def is_subtype(s: TypeExpr, t: TypeExpr) -> bool:
    """Top-level type checking function. `s of? t` => `is_empty(s & ~t)`"""
    return is_empty(intersect(s, negate(t)))




































# def is_nominal_subtype(t: Primitive, target: Primitive) -> bool:
#     """Pure nominal subtype lookup. Check if `t` is a subtype of `target`"""
#     if t == target: return True
#     frontier = [t]
#     while frontier:
#         current = frontier.pop()
#         if current == target: return True
#         frontier.extend(_type_parents[current])
#     return False
    

# # TODO: not quite correct. at least: `(int16 | int32) of? number` should be true but would be false right now...
# #
# def satisfies(t: TypeExpr, target: TypeExpr) -> bool:
#     """Check if `t` satisfies the `target` type expression"""
#     # TODO: t at the moment basically has to be primitive. but can't certain type expressions of t match certain targets?
#     if not isinstance(t, Primitive): print(f'DEBUG WARNING: in `satisfies`, encountered `t` that is not a primitive type. {t=}')

#     if isinstance(target, Primitive):
#         if not isinstance(t, Primitive): 
#             pdb.set_trace() # actually not necessarily false
#             return False
#         return is_nominal_subtype(t, target)
#     if isinstance(target, TypeOr):
#         return any(satisfies(t, item) for item in target.items)
#     if isinstance(target, TypeAnd):
#         return all(satisfies(t, item) for item in target.items)
#     if isinstance(target, TypeNot):
#         return not satisfies(t, target.type)
#     # if isinstance(target, TypeFunc):
#     #     if isinstance(t, TypeFunc):
#     #         return all(satisfies(t_arg, target_arg) for t_arg, target_arg in zip(t.args, target.args)) and satisfies(t.ret, target.ret)
#     #     return False

#     pdb.set_trace()
#     # should be unreachable, but indicates unhandled case
#     return False

# TODO: this will be handled by the dispatch system
# # TODO: come up with canonical names for each operator (e.g. division/mod)
# system_binops: list[tuple[str, TypeExpr, TypeExpr]] = [
#     ('__add__', 'number', 'number'),      #TODO: type here should be anything that is ring or group or ...
#     ('__sub__', 'number', 'number'),
#     ('__mul__', 'number', 'number'),
#     ('__idiv__', 'number', 'number'),
#     ('__mod__', 'number', 'number'),
#     ('__tdiv__', 'number', 'number'),
#     ('__pow__', 'number', 'number'),
   
#     # Don't worry about these for now...    
#     # ('__lshift__', 'int', 'int'),
#     # ('__rshift__', 'int', 'int'),
#     # ('__lrotate__', 'int', 'int'),
#     # ('__rrotate__', 'int', 'int'),
    
#     # ('__eq__', 'any', 'any'),
#     # ('__neq__', 'any', 'any'),
#     # # ('__gt__', 'comparable', 'comparable'),   #TODO: type here is anything that is partial orderable... but also have to be comparable to its own type...
#     # # ('__lt__', 'comparable', 'comparable'),   #      basically what would our notation for traits on generic types be?   <T>   T<traits=comparable>
#     # # ('__gte__', 'comparable', 'comparable'),
#     # # ('__lte__', 'comparable', 'comparable'),   __gt__ = <T has PartialOrder>(left:T right:T):>bool => ...

#     # ('__is__', 'any', 'type'),
#     # ('__isnt__', 'any', 'type'),


#     # TODO: what about iterators  e.g. `x in X and y in Y`
#     ('__and__', 'bool', 'bool'),
#     ('__or__', 'bool', 'bool'),
#     ('__nand__', 'bool', 'bool'),
#     ('__nor__', 'bool', 'bool'),
#     ('__xor__', 'bool', 'bool'),
#     ('__xnor__', 'bool', 'bool'),
# ]


# system_prefixops: list[tuple[str, TypeExpr]] = []
# system_postfixops: list[tuple[str, TypeExpr]] = []




########################################################
# Dispatch System
########################################################


