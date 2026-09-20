"""Persistent source inventory for explicit unchecked assumptions.

The initial report deliberately over-approximates consumers: it lists the
checked operations in each assumption-bearing function, and its direct call
sites. These are review candidates, not a claim that each check logically
needs every assumption. Value facts still use the normal mutation-aware
solver. Collect before reachability/erasure, including cached modules.
"""
from dataclasses import dataclass
import json

from ..reporting import Span, SrcFile
from . import hir


@dataclass(frozen=True)
class Check:
    loc: Span
    kind: str


@dataclass(frozen=True)
class Entry:
    source: SrcFile
    loc: Span
    condition: str
    message: str | None
    scope: str
    checks: tuple[Check, ...]


last_entries: list[Entry] = []


def check_kind(node: hir.AST) -> str | None:
    if isinstance(node, hir.Obligation):
        return 'refinement'
    if isinstance(node, (hir.Index, hir.StringIndex)):
        return 'index'
    if isinstance(node, hir.StringSlice):
        return 'slice'
    if isinstance(node, hir.Assert) and not node.unsafe:
        return 'runtime assertion' if node.runtime else 'assertion'
    if isinstance(node, hir.ValueCast):
        return 'conversion'
    if isinstance(node, hir.FunctionCall) and not node.proof:
        return 'call'  # includes partial arithmetic and transitive callees
    return None


def collect(root: hir.AST, source: SrcFile, scope: str = '<module>') -> list[Entry]:
    entries: list[Entry] = []
    sites: list[hir.Assert] = []
    checks: list[Check] = []
    seen: set[int] = set()
    pending = [root]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, hir.Declare) and isinstance(node.expr, hir.FunctionLiteral):
            entries.extend(collect(node.expr.body, node.expr.source or source, node.name))
            continue
        if isinstance(node, hir.FunctionLiteral):
            entries.extend(collect(node.body, node.source or source, '<anonymous>'))
            continue
        if isinstance(node, hir.Assert) and node.unsafe:
            sites.append(node)
            continue  # terms in the assumption are not its consumers
        elif (kind := check_kind(node)) is not None:
            checks.append(Check(node.loc, kind))
        pending.extend(reversed(list(hir.children(node))))
    unique = {(c.loc.start, c.loc.stop, c.kind): c for c in checks}
    candidates = tuple(unique[key] for key in sorted(unique))
    entries.extend(Entry(source, node.loc, node.source, node.message, scope, candidates) for node in sites)
    return entries


def render(entries: list[Entry]) -> str:
    """A versioned sidecar independent of optimizer and emitted symbols."""
    def location(source: SrcFile, span: Span) -> dict:
        row, column = source.offset_to_row_col(span.start)
        return dict(path=str(source.path) if source.path is not None else None,
                    start=span.start, stop=span.stop, line=row + 1, column=column + 1)
    return json.dumps({
        'version': 1,
        'consumer_precision': 'conservative function scope, not minimal proof dependencies',
        'assumptions': [dict(
            **location(entry.source, entry.loc), condition=entry.condition,
            message=entry.message, scope=entry.scope,
            candidate_checks=[dict(**location(entry.source, check.loc), kind=check.kind) for check in entry.checks],
        ) for entry in entries],
    }, ensure_ascii=False, indent=2) + '\n'
