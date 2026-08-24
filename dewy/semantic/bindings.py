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
    dict_arrays: tuple[int, int] | None = None
    """For a dictionary binding: binding ids of its hidden parallel key and
    value arrays. Dictionaries currently exist only at compile time."""


@dataclass
class BindingRegistry:
    """Allocate identities and retain semantic metadata for checked HIR."""

    next_id: int = 1
    by_id: dict[int, Binding] = field(default_factory=dict)
    by_syntax: dict[int, Binding] = field(default_factory=dict)

    def allocate(
        self,
        syntax: object,
        name: str,
        kind: BindingKind,
        loc: Span,
    ) -> Binding:
        binding = Binding(self.next_id, name, kind, loc)
        self.next_id += 1
        self.by_id[binding.id] = binding
        self.by_syntax[id(syntax)] = binding
        return binding

    def allocate_param(self, name: str, type_: ty.Type, loc: Span) -> Binding:
        binding = Binding(self.next_id, name, 'param', loc, type_)
        self.next_id += 1
        self.by_id[binding.id] = binding
        return binding
