from dataclasses import dataclass, field
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

# Pillars of the type hierarchy
type TopType = Literal['any']
TOP_TYPE: TopType = 'any'
type BottomType = Literal['never']
BOTTOM_TYPE: BottomType = 'never'
type ExceptionType = Literal['exception']
EXCEPTION_TYPE: ExceptionType = 'exception' # parent of all things skipped/forwarded by safe navigation
type TypeType = Literal['type']
TYPE_TYPE: TypeType = 'type'


# Special Types that don't participate in type expressions or the type hierarchy.
type VoidType = Literal['void']  # things cannot be partially void. e.g. `T | void` will always be an error
VOID_TYPE: VoidType = 'void'
type InferredType = Literal['untyped']  # untyped if you want to explicitly indicate it should be inferred, but unannotated things are inferred by default
INFERRED_TYPE: InferredType = 'untyped'


# TODO: probably some sort of Effect base type for the effect system
# type NoReturnEffect = Literal['noreturn']
# NORETURN_EFFECT: NoReturnEffect = 'noreturn'  # NOTE: noreturn is an effect, not a type!




# Dataclasses for type expressions

type Primitive = str   # has to be in the _named_types set


@dataclass
class TypeAnd:
    """type intersection: T1 & T2"""
    items: list[TypeExpr]
    def __post_init__(self):
        assert len(self.items) > 1, f'TypeAnd must have at least two items, got {len(self.items)}'

@dataclass
class TypeOr:
    """type union: T1 | T2"""
    items: list[TypeExpr]
    def __post_init__(self):
        assert len(self.items) > 1, f'TypeOr must have at least two items, got {len(self.items)}'

@dataclass
class TypeNot:
    """type negation: ~T"""
    type: TypeExpr

@dataclass
class TypeParameterize:
    """type parameterization: T<A1 A2 ...>"""
    t: TypeExpr
    args: list[TypeExpr] #TODO: other stuff can be set here, though perhaps it doesn't affect the typing?


# Building blocks for FunctionType / OverloadType (not HIR params, not standalone types)

@dataclass
class PosOrKwArg:
    """One positional-or-keyword slot in a FunctionType.

    Part of the function-type representation: name + accepted argument type.
    Always required (no default). May be filled by position or by name at a call.
    """
    name: str
    type: TypeExpr

@dataclass
class KwOnlyArg:
    """One keyword-only slot in a FunctionType.

    Part of the function-type representation: name + accepted argument type +
    whether a call must supply it. Optional when the surface param has a default;
    required for bare post-`...` kwargs (e.g. forced overwrite via `=void`).
    """
    name: str
    type: TypeExpr
    required: bool

@dataclass
class GenericParam:
    """A generic type variable declared on a FunctionType (e.g. T in `<T of number>`).

    Part of the function-type representation, not a TypeExpr by itself and not
    TypeParameterize (which is applying args like `array<int>`).
    Bound at call sites via infer_type_args / instantiate_method.
    """
    name: str
    bound: TypeExpr = TOP_TYPE

@dataclass
class FunctionType:
    """Type of a single callable: signature shape + return type.

    Built from PosOrKwArg / KwOnlyArg / GenericParam slots (and optional rest).
    This is a TypeExpr atom used in subtyping and dispatch, not an HIR function value.
    """
    pos_or_kw: list[PosOrKwArg]
    kw_only: list[KwOnlyArg]
    rest: str | None  # rest param name, or None
    ret: TypeExpr
    type_params: list[GenericParam] = field(default_factory=list)

@dataclass
class OverloadType:
    """Type of an overloaded callable: an ordered set of FunctionType alternatives.

    Produced by combining callables with `and`/`&` (i.e. function overloading). Still a
    TypeExpr atom; dispatch picks one method at each call site.
    """
    methods: list[FunctionType]
    def __post_init__(self):
        assert len(self.methods) >= 1, 'OverloadType must have at least one method'




type TypeExpr = Primitive | TypeAnd | TypeOr | TypeNot | TypeParameterize | FunctionType | OverloadType
type Type = TypeExpr | VoidType | InferredType # | NoReturnEffect # probably won't ever have a dynamic type, but if we did, it would also go here




# some types to add:
# insert basic types into the system
# note, things like partial order, comparable, etc. will be represented in the structural type system, not the type graph
# TODO: do we support multiple inheritance? probably but TBD
_default_system_types: list[Primitive|tuple[Primitive, Primitive]] = [
    # exceptions
    ('undefined', EXCEPTION_TYPE),
    ('error', EXCEPTION_TYPE),

    # basic types
    'ellipsis',
    'end',
    'new',
    'bool',

    # numbers
    'number',
    ('real', 'number'),
    ('rational', 'real'),
    ('int', 'rational'),
    ('uint', 'int'),
    ('uint8', 'uint'),
    ('uint16', 'uint'),
    ('uint32', 'uint'),
    ('uint64', 'uint'),
    # ('uint128', 'uint'),
    ('int8', 'int'),
    ('int16', 'int'),
    ('int32', 'int'),
    ('int64', 'int'),
    # ('int128', 'int'),
    ('float', 'number'),
    # ('float8', 'float'),
    # ('float16', 'float'),
    ('float32', 'float'),
    ('float64', 'float'),
    # ('float80', 'float'),
    # ('float128', 'float'),
    ('complex', 'number'),   # note: parameterized by the type of its internal representation
    ('quaternion', 'number'), # note: parameterized by the type of its internal representation

    # tbd string stuff
    'char', #'uscalar',     # char # unicode scalar # rune # char # string<length=1>. Not a 'codepoint'
    'grapheme', 
    'string',   # array<unicode_scalar> | array<grapheme>
    # 'istring',  # string with interpolated values. istring probably isn't a separate type? since it should be interchangable with strings
    
    # container types
    'array',
    'dict',
    'set',
    'object',

    # tbd misc stuff
    'ID' # a generic thing representing some way to identify something. implementations may use specific data types like int, string, etc., but conceptually an ID is basically it's own separate thing
]


class TypeSystem:
    def __init__(self, system_types: list[Primitive|tuple[Primitive, Primitive]] = _default_system_types):
        self._named_types: set[str] = {TOP_TYPE, BOTTOM_TYPE, EXCEPTION_TYPE, TYPE_TYPE} # void and inferred don't participate in type expressions
        self._type_parents: dict[str, set[str]] = defaultdict(set, {BOTTOM_TYPE: {TOP_TYPE}, EXCEPTION_TYPE: {TOP_TYPE}, TYPE_TYPE: {TOP_TYPE}})
        self._type_children: dict[str, set[str]] = defaultdict(set, {TOP_TYPE: {BOTTOM_TYPE, EXCEPTION_TYPE, TYPE_TYPE}})
        # order-independent keys via sorted (a, b); separate from the subtype graph
        self._promote_rules: dict[tuple[str, str], str] = {}

        for t in system_types:
            if isinstance(t, tuple): self.add_type(*t) 
            else: self.add_type(t)

    def add_type(self, name: str, parent: str = TOP_TYPE) -> None:
        if name in self._named_types:
            raise ValueError(f'Type {name} already defined')
        self._named_types.add(name)
        self.add_type_link(name, parent)

    def add_type_link(self, child: str, parent: str) -> None:
        if child not in self._named_types:
            raise ValueError(f'Type {child} not defined')
        if parent not in self._named_types:
            raise ValueError(f'Type {parent} not defined')
        self._type_parents[child].add(parent)
        self._type_children[parent].add(child)

    def add_promote_rule(self, a: str, b: str, result: str) -> None:
        """Register promote_type(a, b) == result (order-independent). Extensible for user types."""
        if a not in self._named_types:
            raise ValueError(f'Type {a} not defined')
        if b not in self._named_types:
            raise ValueError(f'Type {b} not defined')
        if result not in self._named_types:
            raise ValueError(f'Type {result} not defined')
        self._promote_rules[tuple(sorted((a, b)))] = result

    def promote_type(self, a: TypeExpr, b: TypeExpr) -> Primitive | None:
        """Common concrete type for heterogeneous arithmetic, or None if none exists.

        Along-edge: if one is a nominal subtype of the other, return the wider.
        Cross-branch: look up an explicit promote rule. Not a lub in the type graph.
        """
        if not isinstance(a, str) or not isinstance(b, str):
            return None
        if a == b:
            return a
        if self._is_nom_subtype(a, b):
            return b
        if self._is_nom_subtype(b, a):
            return a
        return self._promote_rules.get(tuple(sorted((a, b))))
    
    # ---------------------------------------------------------------------------
    # Nominal type theory
    # ---------------------------------------------------------------------------

    def is_subtype(self, s: TypeExpr, t: TypeExpr) -> bool:
        """Top-level type checking function. `s of? t` => `is_empty(s & ~t)`"""
        return self.is_empty(intersect(s, negate(t)))


    def _is_nom_subtype(self, a: Primitive, b: Primitive) -> bool:
        if a == b:
            return True
        frontier = [a]
        seen = {a}
        while frontier:
            cur = frontier.pop()
            for parent in self._type_parents[cur]:
                if parent == b:
                    return True
                if parent not in seen:
                    seen.add(parent)
                    frontier.append(parent)
        return False


    def _meet_prim(self, a: Primitive, b: Primitive) -> Primitive | None:
        """GLB for tree-ish nominal DAG. None => disjoint / uninhabited."""
        if self._is_nom_subtype(a, b):
            return a
        if self._is_nom_subtype(b, a):
            return b
        return None  # unrelated => empty (v1)


    def _meet_atoms(self, a: LiteralAtom, b: LiteralAtom) -> LiteralAtom | None:
        """
        Positive meet of two atoms.
        Covariant TypeParam:
        F<A> & G<B>  (F of? G)  =>  F<A & B>
        F<A> & G<B>  (G of? F)  =>  G<A & B>
        unrelated heads          =>  None (empty)
        Bare prim meets param by treating bare as head with no arg constraint
        array & array<int> => array<int>   if heads meet to array
        Function types only meet when equal; overload combination uses overload_and.
        """
        if isinstance(a, (FunctionType, OverloadType)) or isinstance(b, (FunctionType, OverloadType)):
            return a if a == b else None

        ha, hb = _head_of(a), _head_of(b)
        pa, pb = _as_prim_head(ha), _as_prim_head(hb)
        if pa is None or pb is None:
            # v1: non-primitive heads unsupported / only equal opaque heads
            if ha == hb and _args_of(a) == _args_of(b):
                return a
            return None

        head_meet = self._meet_prim(pa, pb)
        if head_meet is None:
            return None

        args_a, args_b = _args_of(a), _args_of(b)
        if not args_a and not args_b:
            return head_meet
        if not args_a:
            # bare F & G<B...> => head_meet<B...>  (e.g. collection & array<int> => array<int>)
            return TypeParameterize(head_meet, args_b)
        if not args_b:
            return TypeParameterize(head_meet, args_a)

        if len(args_a) != len(args_b):
            return None  # arity mismatch => empty

        # covariant: intersect args pointwise
        meet_args = [intersect(x, y) for x, y in zip(args_a, args_b)]
        # if any arg intersect is never, whole param is never
        if any(self.is_empty(arg) for arg in meet_args):
            # array<never> — treat as empty type in v1 (no values)
            return None
        return TypeParameterize(head_meet, meet_args)


    def _atom_implies_atom(self, a: LiteralAtom, b: LiteralAtom) -> bool:
        """
        Positive atom a is subtype of positive atom b.
        Covariant:
        F<A...> of? G<B...>  ⟺  (F of? G) and all (Ai of? Bi)
        F<A...> of? G        ⟺  F of? G
        F of? G<B...>        ⟺  false   (open world; can't invent args)
        """
        if isinstance(a, (FunctionType, OverloadType)) or isinstance(b, (FunctionType, OverloadType)):
            if isinstance(a, (FunctionType, OverloadType)) and isinstance(b, (FunctionType, OverloadType)):
                return self.callable_subtype(a, b)
            return False

        ha, hb = _head_of(a), _head_of(b)
        pa, pb = _as_prim_head(ha), _as_prim_head(hb)
        args_a, args_b = _args_of(a), _args_of(b)

        if pa is None or pb is None:
            return a == b

        if not self._is_nom_subtype(pa, pb):
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
        return all(self.is_subtype(ai, bi) for ai, bi in zip(args_a, args_b))


    def clause_is_empty(self, clause: DnfClause) -> bool:
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
                meet = self._meet_atoms(meet, atom)
                if meet is None:
                    return True

        if meet == BOTTOM_TYPE:
            return True

        # top with only negatives → non-empty (open world)
        if meet == TOP_TYPE:
            return False

        # P & ~N empty iff P of? N
        for n in neg:
            if self._atom_implies_atom(meet, n):
                return True

        return False


    def is_empty(self, t: TypeExpr) -> bool:
        """True iff t is uninhabited."""
        dnf = normalize(t)
        # prune as we go; all clauses empty => empty type
        return all(self.clause_is_empty(c) for c in dnf)




    ########################################################
    # Function Subtyping
    ########################################################


    def function_subtype(self, f: FunctionType, g: FunctionType) -> bool:
        """True if F is usable wherever G is expected (call-shape inclusion).

        Parameter types are contravariant; return type is covariant.
        Optional kwargs on G cannot be required on F; F may add optional extras.
        """
        if len(f.pos_or_kw) != len(g.pos_or_kw):
            return False
        for fp, gp in zip(f.pos_or_kw, g.pos_or_kw):
            if fp.name != gp.name:
                return False
            if not self.is_subtype(gp.type, fp.type):
                return False

        f_kw = {k.name: k for k in f.kw_only}
        g_kw = {k.name: k for k in g.kw_only}
        g_pos_names = {p.name for p in g.pos_or_kw}

        for name, gk in g_kw.items():
            fk = f_kw.get(name)
            if fk is not None:
                if not self.is_subtype(gk.type, fk.type):
                    return False
                if not gk.required and fk.required:
                    return False
                continue

            fp = next((p for p in f.pos_or_kw if p.name == name), None)
            if fp is not None:
                if not gk.required:
                    return False
                if not self.is_subtype(gk.type, fp.type):
                    return False
                continue

            if f.rest is not None:
                continue
            return False

        for fk in f.kw_only:
            if not fk.required:
                continue
            if fk.name in g_kw or fk.name in g_pos_names:
                continue
            return False

        return self.is_subtype(f.ret, g.ret)


    def callable_subtype(self, f: FunctionType | OverloadType, g: FunctionType | OverloadType) -> bool:
        """Overload coverage: every method in G is covered by some method in F."""
        fs = f.methods if isinstance(f, OverloadType) else [f]
        gs = g.methods if isinstance(g, OverloadType) else [g]
        return all(any(self.function_subtype(fm, gm) for fm in fs) for gm in gs)



    ########################################################
    # Dispatch System
    ########################################################

    def infer_type_args(
        self,
        m: FunctionType,
        pos_types: list[TypeExpr],
        kw_types: dict[str, TypeExpr],
    ) -> dict[str, TypeExpr] | None:
        """Bind generic params from a call. Exact equality for repeated vars; None if impossible."""
        type_vars = {gp.name for gp in m.type_params}
        bindings: dict[str, TypeExpr] = {}

        def match_param(param_t: TypeExpr, arg_t: TypeExpr) -> bool:
            if isinstance(param_t, str) and param_t in type_vars:
                if param_t in bindings:
                    return bindings[param_t] == arg_t
                bindings[param_t] = arg_t
                return True
            return self.is_subtype(arg_t, param_t)

        if len(pos_types) < len(m.pos_or_kw):
            return None
        if len(pos_types) > len(m.pos_or_kw) and m.rest is None:
            return None

        for i, pt in enumerate(pos_types):
            if i < len(m.pos_or_kw) and not match_param(m.pos_or_kw[i].type, pt):
                return None

        pos_names = {p.name for p in m.pos_or_kw}
        kw_map = {k.name: k for k in m.kw_only}

        for name, kt in kw_types.items():
            if name in pos_names:
                p = next(p for p in m.pos_or_kw if p.name == name)
                if not match_param(p.type, kt):
                    return None
                continue
            if name in kw_map:
                if not match_param(kw_map[name].type, kt):
                    return None
                continue
            if m.rest is None:
                return None

        for k in m.kw_only:
            if k.required and k.name not in kw_types:
                return None

        for gp in m.type_params:
            if gp.name not in bindings:
                return None
            if not self.is_subtype(bindings[gp.name], gp.bound):
                return None

        return bindings

    def try_instantiate_for_call(
        self,
        m: FunctionType,
        pos_types: list[TypeExpr],
        kw_types: dict[str, TypeExpr],
    ) -> FunctionType | None:
        """Instantiate generics for this call (if any) and check concrete acceptance."""
        if not m.type_params:
            return m if self.call_accepted_concrete(m, pos_types, kw_types) else None
        bindings = self.infer_type_args(m, pos_types, kw_types)
        if bindings is None:
            return None
        inst = instantiate_method(m, bindings)
        return inst if self.call_accepted_concrete(inst, pos_types, kw_types) else None

    def call_accepted_concrete(self, m: FunctionType, pos_types: list[TypeExpr], kw_types: dict[str, TypeExpr]) -> bool:
        """Whether a fully concrete method accepts this call (no free type params)."""
        if len(pos_types) < len(m.pos_or_kw):
            return False
        if len(pos_types) > len(m.pos_or_kw) and m.rest is None:
            return False

        for i, pt in enumerate(pos_types):
            if i < len(m.pos_or_kw) and not self.is_subtype(pt, m.pos_or_kw[i].type):
                return False

        pos_names = {p.name for p in m.pos_or_kw}
        kw_map = {k.name: k for k in m.kw_only}

        for name, kt in kw_types.items():
            if name in pos_names:
                p = next(p for p in m.pos_or_kw if p.name == name)
                if not self.is_subtype(kt, p.type):
                    return False
                continue
            if name in kw_map:
                if not self.is_subtype(kt, kw_map[name].type):
                    return False
                continue
            if m.rest is None:
                return False

        for k in m.kw_only:
            if k.required and k.name not in kw_types:
                return False
        return True

    def call_accepted(self, m: FunctionType, pos_types: list[TypeExpr], kw_types: dict[str, TypeExpr]) -> bool:
        """Whether a single method accepts this call (instantiating generics if needed)."""
        return self.try_instantiate_for_call(m, pos_types, kw_types) is not None

    def applicable(self, methods: list[FunctionType], pos_types: list[TypeExpr], kw_types: dict[str, TypeExpr]) -> list[FunctionType]:
        """Instantiated methods that accept the call-site argument types."""
        out: list[FunctionType] = []
        for m in methods:
            inst = self.try_instantiate_for_call(m, pos_types, kw_types)
            if inst is not None:
                out.append(inst)
        return out

    def more_specific(self, m1: FunctionType, m2: FunctionType) -> bool:
        """True if m1 is strictly more specific than m2 (positional params only)."""
        if len(m1.pos_or_kw) != len(m2.pos_or_kw):
            return False
        leq = all(self.is_subtype(a.type, b.type) for a, b in zip(m1.pos_or_kw, m2.pos_or_kw))
        geq = all(self.is_subtype(b.type, a.type) for a, b in zip(m1.pos_or_kw, m2.pos_or_kw))
        return leq and not geq

    def match_best_function(
        self,
        methods: list[FunctionType],
        pos_types: list[TypeExpr],
        kw_types: dict[str, TypeExpr] | None = None,
    ) -> 'DispatchResult':
        """Julia-style: unique most-specific applicable method, with promote-and-redispatch fallback."""
        kw_types = kw_types or {}
        apps = self.applicable(methods, pos_types, kw_types)
        promote_pos: list[TypeExpr | None] = [None] * len(pos_types)

        if not apps and pos_types and all(isinstance(t, str) for t in pos_types):
            common: Primitive | None = pos_types[0]  # type: ignore[assignment]
            for t in pos_types[1:]:
                assert common is not None
                common = self.promote_type(common, t)
                if common is None:
                    break
            if common is not None:
                promoted_pos = [common] * len(pos_types)
                apps = self.applicable(methods, promoted_pos, kw_types)
                if apps:
                    promote_pos = [None if t == common else common for t in pos_types]

        if not apps:
            raise DispatchError(f'no matching method for pos={pos_types!r} kw={kw_types!r}')
        winners = [m for m in apps if not any(self.more_specific(o, m) for o in apps if o is not m)]
        if len(winners) != 1:
            raise DispatchError(f'ambiguous call among {len(apps)} applicable methods')
        return DispatchResult(winners[0], promote_pos)





# TODO: want an arbitrary DAG renderer. should draw dags with unicode box drawing characters, no repeated nodes




#######################################################################
# Nominal Type Hierarchy
#######################################################################




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
# TypeParameterize is covariant in all args.
#######################################################################


type LiteralAtom = Primitive | TypeParameterize | FunctionType | OverloadType
# (is_positive, atom)
type DnfClause = tuple[tuple[bool, LiteralAtom], ...]
type Dnf = tuple[DnfClause, ...]  # () == never; ((),) == any (one empty clause)


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
    return TypeAnd(flat)


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
    return TypeOr(flat)


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
    # Primitive | TypeParameterize | FunctionType | OverloadType: keep as Not(atom).
    # Do NOT push not into TypeParameterize args or function signatures.
    return TypeNot(t)


def to_nnf(t: TypeExpr) -> TypeExpr:
    if isinstance(t, TypeNot):
        return negate(t.type)
    if isinstance(t, TypeOr):
        return union(*(to_nnf(x) for x in t.items))
    if isinstance(t, TypeAnd):
        return intersect(*(to_nnf(x) for x in t.items))
    if isinstance(t, TypeParameterize):
        return TypeParameterize(to_nnf(t.t), [to_nnf(a) for a in t.args])
    return t  # Primitive | TypeFunc | TypeOverload | top | bottom


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
    if isinstance(t, (str, TypeParameterize, FunctionType, OverloadType)):
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
# Constructor heads + covariant TypeParam
# ---------------------------------------------------------------------------

def _head_of(atom: LiteralAtom) -> TypeExpr:
    return atom.t if isinstance(atom, TypeParameterize) else atom


def _args_of(atom: LiteralAtom) -> list[TypeExpr]:
    return list(atom.args) if isinstance(atom, TypeParameterize) else []


def _as_prim_head(head: TypeExpr) -> Primitive | None:
    """v1: constructor heads are primitives (array, dict, …)."""
    return head if isinstance(head, str) else None




# ---------------------------------------------------------------------------
# Function types: call-shape subtyping
# ---------------------------------------------------------------------------

# def _methods_of(t: FunctionType | OverloadType) -> list[FunctionType]:
#     return t.methods if isinstance(t, OverloadType) else [t]


# def overload_function(a: FunctionType | OverloadType, b: FunctionType | OverloadType) -> OverloadType:
#     """
#     Create an instance of an overloaded function

#     ```dewy
#     let f = (a:int) => {...}
#     let g = (a:string) => {...}
#     let h = f & g
    
#     h(1)       # calls f
#     h"hello"   # calls g
#     ```

#     > NOTE: this is only meant for combining functions. Other interpretations of the same operators (bitwise, logical, type intersection, etc.) are handled elsewhere.
#     """
#     return OverloadType(_methods_of(a) + _methods_of(b))




class DispatchError(ValueError):
    """No unique most-specific applicable method."""


@dataclass
class DispatchResult:
    """Winning method after dispatch, plus any per-arg promotions to apply before the call."""
    method: FunctionType
    promote_pos: list[TypeExpr | None]  # parallel to call pos_types; None = no promote


def substitute_type(t: TypeExpr, bindings: dict[str, TypeExpr]) -> TypeExpr:
    """Replace free type-param names in a type expression."""
    if isinstance(t, str):
        return bindings.get(t, t)
    if isinstance(t, TypeAnd):
        return TypeAnd([substitute_type(x, bindings) for x in t.items])
    if isinstance(t, TypeOr):
        return TypeOr([substitute_type(x, bindings) for x in t.items])
    if isinstance(t, TypeNot):
        return TypeNot(substitute_type(t.type, bindings))
    if isinstance(t, TypeParameterize):
        return TypeParameterize(substitute_type(t.t, bindings), [substitute_type(a, bindings) for a in t.args])
    if isinstance(t, FunctionType):
        nested_shadow = {gp.name for gp in t.type_params}
        inner = {k: v for k, v in bindings.items() if k not in nested_shadow}
        return FunctionType(
            [PosOrKwArg(p.name, substitute_type(p.type, inner)) for p in t.pos_or_kw],
            [KwOnlyArg(k.name, substitute_type(k.type, inner), k.required) for k in t.kw_only],
            t.rest,
            substitute_type(t.ret, inner),
            list(t.type_params),
        )
    if isinstance(t, OverloadType):
        methods: list[FunctionType] = []
        for m in t.methods:
            sm = substitute_type(m, bindings)
            assert isinstance(sm, FunctionType)
            methods.append(sm)
        return OverloadType(methods)
    raise TypeError(f'substitute_type: unhandled {t!r}')


def instantiate_method(m: FunctionType, type_args: dict[str, TypeExpr]) -> FunctionType:
    """Substitute generic type params, returning a concrete FunctionType."""
    if not m.type_params:
        return m
    return FunctionType(
        [PosOrKwArg(p.name, substitute_type(p.type, type_args)) for p in m.pos_or_kw],
        [KwOnlyArg(k.name, substitute_type(k.type, type_args), k.required) for k in m.kw_only],
        m.rest,
        substitute_type(m.ret, type_args),
        [],
    )





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
