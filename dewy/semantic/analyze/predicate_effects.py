"""Whether an evaluated predicate still describes the current binding values.

Short-circuit operands observe different moments. Reusing the first one's
facts after the second has written one of its inputs would describe the old
value. Track whole roots conservatively, including projected writes; the
ordinary refinement rules remain responsible for extracting the actual facts.
"""

from .. import bindings as sb
from .. import hir


def write_target(node: hir.AST) -> hir.AST | None:
    """Storage a local operation may write, before interprocedural summaries."""
    if isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign, hir.Place)):
        return node.target
    if isinstance(node, (hir.DictStore, hir.DictRemove)):
        return node.keys
    if isinstance(node, hir.FunctionCall):
        if isinstance(node.func, hir.ArrayMethod) and node.func.name != 'join':
            return node.func.array
        if isinstance(node.func, hir.DictMethod) and node.func.name in {'add', 'clear', 'remove'}:
            return node.func.dictionary
    return None


def _binding_effects(root: hir.AST, *, reads: bool, writes: bool, call_writes: dict[int, set[int]] | None = None, read_only_places: set[int] | frozenset[int] = frozenset()) -> tuple[set[int], set[int]]:
    read: set[int] = set()
    written: set[int] = set()
    pending = [root]
    while pending:
        node = pending.pop()
        if isinstance(node, hir.FunctionLiteral):
            continue
        if reads and isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
            read.add(node.binding_id)
        if writes:
            target = write_target(node)
            if isinstance(node, hir.Place) and id(node) in read_only_places:
                target = None
            if isinstance(node, hir.FunctionCall) and call_writes is not None:
                written.update(call_writes.get(id(node), ()))
            if target is not None:
                access = sb.access_path(target, unwrap=sb._unwrap_fact_route)
                if isinstance(access.root, hir.ExpressedIdentifier) and access.root.binding_id is not None:
                    written.add(access.root.binding_id)
        pending.extend(hir.children(node))
    return read, written


def read_bindings(root: hir.AST) -> set[int]:
    return _binding_effects(root, reads=True, writes=False)[0]


def mutated_bindings(root: hir.AST, *, call_writes: dict[int, set[int]] | None = None,
                     read_only_places: set[int] | frozenset[int] = frozenset()) -> set[int]:
    return _binding_effects(root, reads=False, writes=True, call_writes=call_writes,
                           read_only_places=read_only_places)[1]


class BindingQueries:
    """Reuse syntactic predicate queries during one stable-tree analysis.

    HIR is mutable, so the checker uses the uncached functions above while
    constructing it. A bounds validator owns this cache only for its pass;
    recording a proven constant index does not change binding reads/writes.
    It must not survive a structural rewrite or binding-identity remapping.
    """

    def __init__(self, call_writes: dict[int, set[int]] | None = None):
        self.call_writes = call_writes
        self.entries: dict[int, tuple[hir.AST, frozenset[int], frozenset[int]]] = {}

    def _query(self, root: hir.AST) -> tuple[hir.AST, frozenset[int], frozenset[int]]:
        entry = self.entries.get(id(root))
        if entry is None:
            reads, writes = _binding_effects(root, reads=True, writes=True, call_writes=self.call_writes)
            entry = (root, frozenset(reads), frozenset(writes))
            self.entries[id(root)] = entry   # retain the node against identity reuse
        return entry

    def read_bindings(self, root: hir.AST) -> frozenset[int]:
        return self._query(root)[1]

    def mutated_bindings(self, root: hir.AST) -> frozenset[int]:
        return self._query(root)[2]
