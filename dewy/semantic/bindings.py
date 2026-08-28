"""Stable source binding identities shared by semantic analyses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..reporting import Span
from . import hir, ty


BindingKind = Literal['value', 'function', 'overload', 'param']


@dataclass
class Binding:
    """One source declaration independently of its initialization state."""

    id: int
    name: str
    kind: BindingKind
    loc: Span
    type: ty.Type | None = None
    type_value: ty.TypeAliasValue | None = None
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
    route_root: int | None = None
    """For a hidden *route* binding (`bag.items`): the root binding's id.
    Length and index facts are keyed by these ids so member arrays get the
    same proofs as named arrays; assigning the root or a prefix drops them."""


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


def array_route_id(node: hir.AST, registry: BindingRegistry) -> int | None:
    """The fact id of a runtime-length array expression.

    A named array is its binding id; a chain of member accesses rooted at a
    named binding (`bag.items`) is a hidden route id. Anything else has no
    stable identity for length facts.
    """
    while isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Obligation)):
        node = node.expr if not isinstance(node, hir.Obligation) else node.value
    if isinstance(node, hir.ExpressedIdentifier):
        return node.binding_id
    path: list[str] = []
    current = node
    while isinstance(current, hir.MemberAccess):
        path.append(current.name)
        current = current.value
    if not path or not isinstance(current, hir.ExpressedIdentifier) or current.binding_id is None:
        return None
    if current.binding_id not in registry.by_id:
        return None
    return registry.route_id(current.binding_id, tuple(reversed(path)), node.type, node.loc)


def member_path(node: hir.AST) -> tuple[int, tuple[str, ...]] | None:
    """The (root binding id, field path) of a member-access chain, if it has one."""
    path: list[str] = []
    current = node
    while isinstance(current, hir.MemberAccess):
        path.append(current.name)
        current = current.value
    if isinstance(current, hir.ExpressedIdentifier) and current.binding_id is not None:
        return current.binding_id, tuple(reversed(path))
    return None
