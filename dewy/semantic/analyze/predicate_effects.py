"""Whether an evaluated predicate still describes the current binding values.

Short-circuit operands observe different moments. Reusing the first one's
facts after the second has written one of its inputs would describe the old
value. Track whole roots conservatively, including projected writes; the
ordinary refinement rules remain responsible for extracting the actual facts.
"""

from .. import bindings as sb
from .. import hir
from .effects import _iter_children


def read_bindings(root: hir.AST) -> set[int]:
    result: set[int] = set()
    pending = [root]
    while pending:
        node = pending.pop()
        if isinstance(node, hir.FunctionLiteral):
            continue
        if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
            result.add(node.binding_id)
        pending.extend(_iter_children(node))
    return result


def mutated_bindings(root: hir.AST) -> set[int]:
    result: set[int] = set()
    pending = [root]
    while pending:
        node = pending.pop()
        if isinstance(node, hir.FunctionLiteral):
            continue
        target = None
        if isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign, hir.Place)):
            target = node.target
        elif isinstance(node, (hir.DictStore, hir.DictRemove)):
            target = node.keys
        elif isinstance(node, hir.FunctionCall):
            if isinstance(node.func, hir.ArrayMethod) and node.func.name != 'join':
                target = node.func.array
            elif isinstance(node.func, hir.DictMethod) and node.func.name in {'add', 'clear', 'remove'}:
                target = node.func.dictionary
        if target is not None:
            access = sb.access_path(target, unwrap=sb._unwrap_fact_route)
            if isinstance(access.root, hir.ExpressedIdentifier) and access.root.binding_id is not None:
                result.add(access.root.binding_id)
        pending.extend(_iter_children(node))
    return result
