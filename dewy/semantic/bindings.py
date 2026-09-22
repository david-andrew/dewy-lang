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
    """A parameter's declared storage contract, before flow narrowing.
    Both private values and borrowed places retain their written annotation;
    a place additionally owes that contract to the caller's storage."""
    type_value: ty.TypeAliasValue | None = None
    effect_value: effect_rows.Contract | None = None
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
    # A const selector can be rebound on the next execution of its declaration
    # (for example in a loop). Its dependent routes must lose old evidence.
    index_routes: dict[int, set[int]] = field(default_factory=dict)

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
        """Descendants of a route; mutation-only ``[]`` matches any selector."""
        return [
            route_id
            for route_id in self.routes_by_root.get(root_id, ())
            if len(self.route_paths[route_id]) >= len(prefix)
            and all(left == right or left == '[]' and right.startswith('[')
                    for left, right in zip(prefix, self.route_paths[route_id]))
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


type AccessComponent = tuple[Literal['field'], str] | tuple[Literal['index'], int | None] | tuple[Literal['key'], None]
type AccessStep = hir.MemberAccess | hir.ForwardingAccess | hir.Index | hir.DictLookup


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
            ('key', None) if isinstance(step, hir.DictLookup)
            else ('index', step.constant_index) if isinstance(step, hir.Index)
            else ('field', step.name if isinstance(step, hir.MemberAccess) else step.field)
            for step in self.steps
        )

    @property
    def fields(self) -> tuple[str, ...] | None:
        """A pure member path, or None if an index intervenes."""
        names: list[str] = []
        for step in self.steps:
            if isinstance(step, (hir.Index, hir.DictLookup)):
                return None
            names.append(step.name if isinstance(step, hir.MemberAccess) else step.field)
        return tuple(names)


def access_path(
    node: hir.AST,
    *,
    unwrap: Callable[[hir.AST], hir.AST] = lambda node: node,
    forwarding: bool = False,
    dictionaries: bool = False,
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
        elif dictionaries and isinstance(node, hir.DictLookup) and node.proven:
            steps.append(node)
            node = node.values
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
    """The fact id of a named sequence and stable field/index route.

    Use ``create=False`` for reads that only consume an existing route fact.
    A const selector identifies one evaluated index until its declaration is
    executed again. Bracketed components cannot collide with field names.
    """
    path = access_path(node, unwrap=_unwrap_fact_route, dictionaries=True)
    root_id = path.binding_id
    if root_id is None:
        return None
    names = []
    indices = []
    for step in path.steps:
        if isinstance(step, hir.DictLookup):
            selected = _unwrap_fact_route(step.key)
            if isinstance(selected, hir.Integer):
                names.append(f"[key:i{selected.value}]")
            elif isinstance(selected, hir.String):
                names.append(f"[key:s{len(selected.content)}:{selected.content}]")
            else:
                binding = registry.by_id.get(selected.binding_id) if isinstance(selected, hir.ExpressedIdentifier) else None
                if binding is None or binding.declaration is None or binding.declaration.decltype != 'const':
                    return None
                names.append(f"[key:@{binding.id}]")
                indices.append(binding.id)
        elif isinstance(step, hir.Index):
            selected = _unwrap_fact_route(step.index)
            if isinstance(selected, hir.Integer):
                # Literal routes must exist during inference too, before
                # validation records an optional constant-index optimization.
                names.append(f'[{selected.value}]')
            elif step.constant_index is not None:
                names.append(f'[{step.constant_index}]')
            else:
                binding = registry.by_id.get(selected.binding_id) if isinstance(selected, hir.ExpressedIdentifier) else None
                if binding is None or binding.declaration is None or binding.declaration.decltype != 'const':
                    return None
                names.append(f'[@{binding.id}]')
                indices.append(binding.id)
        else:
            names.append(step.name)
    fields = tuple(names)
    if not fields:
        return root_id
    if root_id not in registry.by_id:
        return None
    if not create:
        return registry.route_ids.get((root_id, fields))
    result = registry.route_id(root_id, fields, node.type, node.loc)
    for index in indices:
        registry.index_routes.setdefault(index, set()).add(result)
    return result


def mutation_path(node: hir.AST) -> tuple[int, tuple[str, ...]] | None:
    """A write affects possibly aliased selectors but preserves ancestor facts."""
    path = access_path(node, unwrap=_unwrap_fact_route, dictionaries=True)
    if path.binding_id is None:
        return None
    return path.binding_id, tuple(step.name if isinstance(step, hir.MemberAccess) else '[]' for step in path.steps)


def member_path(node: hir.AST) -> tuple[int, tuple[str, ...]] | None:
    """The (root binding id, field path) of an unwrapped member-access chain."""
    path = access_path(node)
    root_id, fields = path.binding_id, path.fields
    return (root_id, fields) if root_id is not None and fields is not None else None


def local_place_containers(binding_id: int, registry: BindingRegistry) -> set[int]:
    """Ancestor dictionaries whose keys survive a write through this alias."""
    result = set()
    seen = set()
    while binding_id not in seen:
        seen.add(binding_id)
        binding = registry.by_id.get(binding_id)
        declaration = binding.declaration if binding is not None else None
        if declaration is None or not declaration.view:
            break
        path = access_path(declaration.expr, unwrap=_unwrap_fact_route, dictionaries=True)
        for step in path.steps:
            if isinstance(step, hir.DictLookup) and isinstance(step.keys, hir.MemberAccess):
                container = array_route_id(step.keys.value, registry)
                if container is not None:
                    result.add(container)
        binding_id = path.binding_id
    return result
