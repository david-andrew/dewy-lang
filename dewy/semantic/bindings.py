"""Stable source binding identities shared by semantic analyses."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from ..reporting import Span
from . import effect_rows, hir, ty

BindingKind = Literal['value', 'function', 'overload', 'param', 'effect']


@dataclass
class Binding:
    """One source declaration independently of its initialization state."""

    id: int
    name: str
    kind: BindingKind
    loc: Span
    type: ty.Type | None = None
    store_type: ty.Type | None = None
    """A place parameter's declared storage contract, before flow narrowing.
    Unlike a value parameter's copied local, every write remains constrained
    by the caller's storage type, including scalar refinements."""
    type_value: ty.TypeAliasValue | None = None
    effect_value: effect_rows.Row | None = None
    declaration: hir.Declare | None = None
    function: hir.FunctionLiteral | None = None
    literal_path_parameter: str | None = None
    read_only_reason: str | None = None
    syntax: object = None
    """The syntax object this binding was allocated for. Held so the object
    stays alive for the registry's lifetime: `by_syntax` is keyed by `id()`,
    and a freed object's id could otherwise be reused by unrelated syntax."""
    """Why the binding cannot be written, when it is not a `const` declaration
    (a loop variable borrowing an array element)."""
    generic_instance: object = None
    """For an instance of a generic function: `(generic, type_arguments, ctx)` —
    the `hir.GenericFunction`, its bindings, and the checking context of the
    call that created it — so a later pass can instantiate the generic again
    for other types (the representation pass, when an argument becomes big)."""
    nominal_name: str | None = None
    """The identity minted by this declaration. Spelling alone cannot identify
    a type: two modules (or nested scopes) can each declare their own Token."""
    route_root: int | None = None
    """For a hidden *route* binding (`bag.items`): the root binding's id.
    Length and index facts are keyed by these ids so member arrays get the
    same proofs as named arrays; assigning the root or a prefix drops them."""
    proof: bool = False
    """A checked, erased proof declaration, never an ordinary function value."""


@dataclass
class BindingRegistry:
    """Allocate identities and retain semantic metadata for checked HIR."""

    next_id: int = 1
    next_route_id: int = 1 << 19  # member-route bindings (see `route_id`); ids stay below the bounds analysis's 20-bit fact packing
    by_id: dict[int, Binding] = field(default_factory=dict)
    by_syntax: dict[int, Binding] = field(default_factory=dict)
    route_ids: dict[tuple[int, tuple[str, ...]], int] = field(default_factory=dict)
    routes_by_root: dict[int, list[int]] = field(default_factory=dict)
    route_paths: dict[int, tuple[str, ...]] = field(default_factory=dict)

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        # Object addresses belong to the process that wrote the cache. The
        # syntax itself is retained by each binding and restored by pickle;
        # rebuild its index before any newly parsed syntax can reuse an old
        # address and accidentally complete an unrelated binding.
        self.by_syntax = {id(binding.syntax): binding for binding in self.by_syntax.values()}

    def route_id(self, root_id: int, path: tuple[str, ...], type_: ty.Type, loc: Span) -> int:
        """A stable id for the member route ``root.path``, allocated on first use."""
        key = (root_id, path)
        existing = self.route_ids.get(key)
        if existing is not None:
            return existing
        root = self.by_id[root_id]
        # routes have their own id range: they are allocated lazily (also by
        # the analyses after checking), so sharing `next_id` would let a
        # validation-only compile shift every later binding id
        binding = Binding(self.next_route_id, f'{root.name}.{".".join(path)}', 'value', loc, type_)
        binding.route_root = root_id
        self.next_route_id += 1
        self.by_id[binding.id] = binding
        self.route_ids[key] = binding.id
        self.routes_by_root.setdefault(root_id, []).append(binding.id)
        self.route_paths[binding.id] = path
        return binding.id

    def routes_under(self, root_id: int, prefix: tuple[str, ...] = ()) -> list[int]:
        """Route ids rooted at ``root_id`` whose path starts with ``prefix``."""
        return [
            route_id
            for route_id in self.routes_by_root.get(root_id, ())
            if self.route_paths[route_id][:len(prefix)] == prefix
        ]

    def allocate(
        self,
        syntax: object,
        name: str,
        kind: BindingKind,
        loc: Span,
    ) -> Binding:
        binding = Binding(self.next_id, name, kind, loc)
        binding.syntax = syntax
        self.next_id += 1
        self.by_id[binding.id] = binding
        self.by_syntax[id(syntax)] = binding
        return binding

    def allocate_param(self, name: str, type_: ty.Type, loc: Span) -> Binding:
        binding = Binding(self.next_id, name, 'param', loc, type_)
        self.next_id += 1
        self.by_id[binding.id] = binding
        return binding


type AccessComponent = tuple[Literal['field'], str] | tuple[Literal['index'], int | None]
type AccessStep = hir.MemberAccess | hir.ForwardingAccess | hir.Index


@dataclass(frozen=True)
class AccessPath:
    """A root expression and its access steps in root-to-leaf order.

    Keep the HIR steps so consumers can inspect owner types and evaluate
    index expressions. A path need not have a stable binding as its root.
    """

    root: hir.AST
    steps: tuple[AccessStep, ...]

    @property
    def binding_id(self) -> int | None:
        return self.root.binding_id if isinstance(self.root, hir.ExpressedIdentifier) else None

    @property
    def components(self) -> tuple[AccessComponent, ...]:
        return tuple(
            ('index', step.constant_index) if isinstance(step, hir.Index)
            else ('field', step.name if isinstance(step, hir.MemberAccess) else step.field)
            for step in self.steps
        )

    @property
    def fields(self) -> tuple[str, ...] | None:
        """A pure member path, or None if an index intervenes."""
        names: list[str] = []
        for step in self.steps:
            if isinstance(step, hir.Index):
                return None
            names.append(step.name if isinstance(step, hir.MemberAccess) else step.field)
        return tuple(names)


def access_path(
    node: hir.AST,
    *,
    unwrap: Callable[[hir.AST], hir.AST] = lambda node: node,
    forwarding: bool = False,
) -> AccessPath:
    """Decompose access syntax with an explicit consumer-specific cast policy.

    No casts are transparent by default: preserving a storage route and
    preserving numerical facts are different questions.
    """
    steps: list[AccessStep] = []
    while True:
        node = unwrap(node)
        if isinstance(node, hir.MemberAccess) or forwarding and isinstance(node, hir.ForwardingAccess):
            steps.append(node)
            node = node.value
        elif isinstance(node, hir.Index):
            steps.append(node)
            node = node.array
        else:
            return AccessPath(node, tuple(reversed(steps)))


def _unwrap_fact_route(node: hir.AST) -> hir.AST:
    """Views through which sequence identity is tracked (not a value evaluator)."""
    while isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Obligation)):
        node = node.value if isinstance(node, hir.Obligation) else node.expr
    return node


def field_route(node: hir.AST, fields: tuple[str, ...]) -> hir.AST | None:
    """Resolve a pure, statically known field route without evaluating it.

    Refinement terms use this when rebinding a parameter's nested length to
    its actual argument. An optional or otherwise ambiguous receiver cannot
    establish that route without a narrowing at the source expression.
    """
    for name in fields:
        record = ty.unfold(ty.strip_refinement(node.type))
        if not isinstance(record, ty.ObjectType) or (record.brand is not None and not ty.user_branded(record)):
            return None
        member = record.field(name)
        if member is None:
            return None
        node = hir.MemberAccess(node.loc, member.type, node, name, member.mutable)
    return node


def array_route_id(node: hir.AST, registry: BindingRegistry, *, create: bool = True) -> int | None:
    """The fact id of a named sequence and stable field/constant-index route.

    Use ``create=False`` for reads that only consume an existing route fact.
    Bracketed components cannot collide with field names. A dynamic index
    needs an identity tied to its current value; it is not stable here yet.
    """
    path = access_path(node, unwrap=_unwrap_fact_route)
    root_id = path.binding_id
    if root_id is None:
        return None
    names = []
    for step in path.steps:
        if isinstance(step, hir.Index):
            if step.constant_index is None:
                return None
            names.append(f'[{step.constant_index}]')
        else:
            names.append(step.name)
    fields = tuple(names)
    if not fields:
        return root_id
    if root_id not in registry.by_id:
        return None
    if not create:
        return registry.route_ids.get((root_id, fields))
    return registry.route_id(root_id, fields, node.type, node.loc)


def member_path(node: hir.AST) -> tuple[int, tuple[str, ...]] | None:
    """The (root binding id, field path) of an unwrapped member-access chain."""
    path = access_path(node)
    root_id, fields = path.binding_id, path.fields
    return (root_id, fields) if root_id is not None and fields is not None else None
