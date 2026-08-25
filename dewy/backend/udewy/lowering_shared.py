"""Shared layout constants and lowering data structures.

Split from ``lower.py``; see that module's docstring for the overall design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...semantic import hir

ARRAY_DATA_OFFSET = 0

ARRAY_LENGTH_OFFSET = 8

ARRAY_CAPACITY_OFFSET = 16

ARRAY_STRIDE_OFFSET = 24

ARRAY_FLAGS_OFFSET = 32

ARRAY_OWNER_OFFSET = 40

ARRAY_DESCRIPTOR_SIZE = 48

ARRAY_MUTABLE = 1

ARRAY_BORROWED_STATIC = 2

type ArrayRepresentation = Literal[
    'descriptor',
    'stack_data',
    'static_words',
    'static_bytes',
]

type ArrayUse = Literal[
    'length',
    'grow',
    'index_read',
    'index_write',
    'alias',
    'call_boundary_pending',
    'safe_call_boundary',
    'copy_call_boundary',
    'representation',
]

STRING_DATA_OFFSET = 0

STRING_BYTE_LENGTH_OFFSET = 8

STRING_BOUNDARIES_OFFSET = 16

STRING_GRAPHEME_LENGTH_OFFSET = 24

STRING_START_OFFSET = 32

STRING_DESCRIPTOR_SIZE = 40

FIXED_INTEGER_WIDTHS = {
    'int8': 8,
    'int16': 16,
    'int32': 32,
    'int64': 64,
    'uint8': 8,
    'uint16': 16,
    'uint32': 32,
    'uint64': 64,
}

SIGNED_FIXED_INTS = {'int8', 'int16', 'int32', 'int64'}

@dataclass
class LoweredFunction:
    """One concrete function that the udewy backend must emit at module scope."""

    symbol: str
    literal: hir.FunctionLiteral

@dataclass
class LoweredProgram:
    """Result of callable legalization.

    ``functions`` contains every original top-level function plus hoisted local
    and inline alternatives. ``globals`` contains module storage declarations,
    while ``startup_items`` initializes that storage and executes other
    top-level code in source order.
    """

    functions: list[LoweredFunction]
    globals: list[hir.Declare]
    startup_items: list[hir.AST]
    user_main_symbol: str | None
    startup_symbol: str
    needs_startup: bool

@dataclass
class _Scope:
    """A reconstructed lexical scope used to resolve mutable, unbound HIR names.

    HIR identifiers currently retain only their source spelling and type, not a
    definition ID. The lowering pass therefore mirrors semantic scope rules and
    records the binding selected for each identifier occurrence.

    ``display_path`` is a readable lexical path used only when symbol
    disambiguation requires scope qualification. The first function-body block
    is transparent in that path; nested anonymous blocks use ``scope_N``.
    """

    parent: _Scope | None
    display_path: tuple[str, ...]
    owner_function: _FunctionDef | None
    bindings: dict[str, _Binding]
    next_block_ordinal: int = 1

    def resolve(self, name: str) -> _Binding | None:
        """Return the nearest lexical binding for ``name``."""
        scope: _Scope | None = self
        while scope is not None:
            if name in scope.bindings:
                return scope.bindings[name]
            scope = scope.parent
        return None

@dataclass
class _Binding:
    """A declaration reconstructed from HIR.

    ``kind`` distinguishes parameters and ordinary values from function and
    compile-time overload bindings. ``owner_function`` identifies values that
    would need closure capture when referenced by another function.
    """

    order: int
    name: str
    kind: str
    owner_function: _FunctionDef | None
    expr: hir.AST | None
    semantic_id: int | None
    function: _FunctionDef | None = None
    emitted_name: str | None = None

@dataclass
class _FunctionDef:
    """Internal identity for a concrete function before its symbol is chosen.

    ``logical_name`` is the source binding name, or ``anon`` for a bare
    function expression. Inline overload alternatives share their overload
    binding's logical name and set ``overload_member`` so their signatures
    participate in mangling.
    """

    order: int
    logical_name: str
    literal: hir.FunctionLiteral
    definition_scope: _Scope
    overload_member: bool
    symbol: str = ''
    result_name: str | None = None

@dataclass(frozen=True)
class ArrayParameterAnalysis:
    function: _FunctionDef
    parameter: hir.Param
    alias_group: frozenset[int]
    uses: frozenset[ArrayUse]
    adapter_safe: bool

@dataclass(frozen=True)
class ArrayCallBoundaryAnalysis:
    function: _FunctionDef | None
    argument: hir.AST
    position: int | str
    parameter: hir.Param | None
    source_binding_id: int | None
    source_alias_group: frozenset[int]
    safe: bool


@dataclass(frozen=True)
class StringResultBound:
    """Compile-time capacity bound for one string value.

    ``const_bytes`` plus, for each positional parameter index, ``counts[i]``
    times the runtime byte length of that string argument bounds the UTF-8
    byte size of the value. ``materialized`` records whether the value may be
    backed by frame-local materialized storage, in which case returning it
    requires caller-owned result storage.
    """

    const_bytes: int
    counts: tuple[tuple[int, int], ...]
    materialized: bool

    def combined_max(self, other: StringResultBound) -> StringResultBound:
        counts: dict[int, int] = dict(self.counts)
        for index, count in other.counts:
            counts[index] = max(counts.get(index, 0), count)
        return StringResultBound(
            max(self.const_bytes, other.const_bytes),
            tuple(sorted(counts.items())),
            self.materialized or other.materialized,
        )

    def combined_sum(self, other: StringResultBound) -> StringResultBound:
        counts: dict[int, int] = dict(self.counts)
        for index, count in other.counts:
            counts[index] = counts.get(index, 0) + count
        return StringResultBound(
            self.const_bytes + other.const_bytes,
            tuple(sorted(counts.items())),
            self.materialized or other.materialized,
        )
