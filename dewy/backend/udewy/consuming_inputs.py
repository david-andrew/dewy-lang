"""Direct-call ownership inputs whose sole use transfers the incoming value.

This is a private calling convention, not a source effect or ownership tag.
Every caller materializes an independent argument and the callee owns it.
The native lowerer uses the same single-use rule in borrowing.dewy. Ordinary
mutable inputs and conditional/loop consumption retain their other protocols.
"""
from collections import defaultdict, deque

from ...semantic import hir, ty
from ...semantic.analyze.effects import _literal_params
from ...semantic.analyze.storage_borrows import borrowable


def record_parameters(analysis, excluded_literals):
    """Find record inputs donated into push/insert or another proved input.

    A worklist propagates only from actual consuming operations. A forwarding
    cycle without a consuming endpoint supplies no evidence. Functions used
    as values or capturing surrounding storage are excluded by the caller.
    """
    candidates = {}
    for literal in analysis.literals:
        if id(literal) in excluded_literals or literal.object_receiver:
            continue
        wanted = {p.binding_id for p in _literal_params(literal)
                  if p.binding_id is not None and not p.place
                  and not isinstance(p, hir.BoundParam)
                  and isinstance(ty.structural_base(p.type), ty.ObjectType)
                  and borrowable(p.type)}
        if not wanted:
            continue
        reads = defaultdict(list)
        exited = False

        def visit(node, parent=None, guarded=False):
            nonlocal exited
            if isinstance(node, hir.ExpressedIdentifier):
                if node.binding_id in wanted:
                    reads[node.binding_id].append((node, parent, guarded or exited))
                return
            nested = guarded or isinstance(node, (hir.FunctionLiteral, hir.Flow,
                                                   hir.IfArm, hir.LoopArm, hir.ShortCircuit))
            for child in hir.children(node):
                visit(child, node, nested)
            if isinstance(node, hir.Return):
                exited = True

        # Defaults can execute conditionally. Do not ignore an additional
        # reference there even though the donating parameter has no default.
        for param in _literal_params(literal):
            if isinstance(param, hir.BoundParam):
                visit(param.value, guarded=True)
        visit(literal.body)
        for binding, sites in reads.items():
            if len(sites) == 1 and not sites[0][2]:
                candidates[binding] = sites[0][:2]

    proven = set()
    dependents = defaultdict(set)
    for binding, (read, parent) in candidates.items():
        if not isinstance(parent, hir.FunctionCall):
            continue
        if isinstance(parent.func, hir.ArrayMethod):
            if (parent.func.name in {'push', 'insert'} and parent.pos_args
                    and parent.pos_args[0] is read):
                proven.add(binding)
            continue
        targets = analysis._direct_targets(parent)
        if targets is None or len(targets) != 1:
            continue
        for argument, parameter in analysis._pair_arguments(parent, targets[0]) or ():
            if argument is read and parameter is not None and parameter.binding_id in candidates:
                dependents[parameter.binding_id].add(binding)
    pending = deque(proven)
    while pending:
        for binding in dependents.get(pending.popleft(), ()):
            if binding not in proven:
                proven.add(binding)
                pending.append(binding)
    return proven
