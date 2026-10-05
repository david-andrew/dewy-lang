"""Persistent source inventory for explicit unchecked assumptions.

Each assumption lists its demonstrated consumers: the checks that become
undecided when the bounds checker validates the program again without it
(`bounds.assumption_consumers`). The checked operations of its function stay
listed as review candidates. Value facts still use the normal mutation-aware
solver. Collect before reachability/erasure, including cached modules; an
assumption in the prelude, whose checks are cached, has no consumer list.
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
    consumers: tuple[Check, ...] | None = None


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


def collect(root: hir.AST, source: SrcFile, scope: str = '<module>', *, consumers: dict | None = None) -> list[Entry]:
    entries: list[Entry] = []
    sites: list[hir.Assert] = []
    checks: list[Check] = []
    seen: set[int] = set()
    # Defaults are executable children of the function too. Start inside the
    # function boundary, so its defaults and body share one audit scope while
    # nested functions still open their own scopes.
    pending = list(reversed(tuple(hir.children(root)))) if isinstance(root, hir.FunctionLiteral) else [root]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, hir.Declare) and isinstance(node.expr, hir.FunctionLiteral):
            entries.extend(collect(node.expr, node.expr.source or source, node.name, consumers=consumers))
            continue
        if isinstance(node, hir.FunctionLiteral):
            entries.extend(collect(node, node.source or source, '<anonymous>', consumers=consumers))
            continue
        if isinstance(node, hir.Assert) and node.unsafe:
            sites.append(node)
            continue  # terms in the assumption are not its consumers
        elif (kind := check_kind(node)) is not None:
            checks.append(Check(node.loc, kind))
        pending.extend(reversed(list(hir.children(node))))
    unique = {(c.loc.start, c.loc.stop, c.kind): c for c in checks}
    candidates = tuple(unique[key] for key in sorted(unique))
    def demonstrated(node: hir.Assert) -> tuple[Check, ...] | None:
        found = (consumers or {}).get(id(node))
        if found is None:
            return None
        unique = {(site.loc.start, site.loc.stop, check_kind(site) or 'check'): Check(site.loc, check_kind(site) or 'check') for site in found}
        return tuple(unique[key] for key in sorted(unique))
    entries.extend(Entry(source, node.loc, node.source, node.message, scope, candidates, demonstrated(node)) for node in sites)
    return entries


def render(entries: list[Entry]) -> str:
    """A versioned sidecar independent of optimizer and emitted symbols."""
    def location(source: SrcFile, span: Span) -> dict:
        row, column = source.offset_to_row_col(span.start)
        return dict(path=str(source.path) if source.path is not None else None,
                    start=span.start, stop=span.stop, line=row + 1, column=column + 1)
    return json.dumps({
        'version': 2,
        'consumer_precision': 'consumers: checks undecided without this assumption; candidate_checks: the checked operations of its function',
        'assumptions': [dict(
            **location(entry.source, entry.loc), condition=entry.condition,
            message=entry.message, scope=entry.scope,
            candidate_checks=[dict(**location(entry.source, check.loc), kind=check.kind) for check in entry.checks],
            consumers=None if entry.consumers is None else [dict(**location(entry.source, check.loc), kind=check.kind) for check in entry.consumers],
        ) for entry in entries],
    }, ensure_ascii=False, indent=2) + '\n'
