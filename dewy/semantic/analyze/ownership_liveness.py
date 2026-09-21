"""Path-sensitive last uses for logical resource ownership.

The storage lowerer still decides how bytes travel. This analysis decides
whether a resource may change owners, so cleanup can follow the executed path.
Loop backedges retain outer owners; locals are born anew each iteration.
Aliases and captures keep their root live, while returns have no backedge. No traversal order is treated as a branch join.
"""
from .. import hir


def conditional_consumptions(body, parameter_owners, resource):
    nodes, owners, aliases, captured, occurrences = [], set(), {}, set(), {}
    owners.update(p.binding_id for p in parameter_owners)
    pending = [body]
    while pending:
        node = pending.pop()
        nodes.append(node)
        if isinstance(node, hir.FunctionLiteral):
            captured.update(n.binding_id for n in hir.walk(node) if isinstance(n, hir.ExpressedIdentifier))
            continue
        if isinstance(node, hir.ExpressedIdentifier):
            occurrences[id(node)] = occurrences.get(id(node), 0) + 1
        if isinstance(node, hir.Declare) and resource(node.annotation or node.expr.type) is not None:
            owners.add(node.binding_id)
            if isinstance(node.expr, hir.ExpressedIdentifier):
                aliases[node.binding_id] = node.expr.binding_id
        pending.extend(hir.children(node))

    def roots(binding):
        result = set()
        while binding is not None and binding not in result:
            result.add(binding)
            binding = aliases.get(binding)
        return result

    def reads(node):
        result = set()
        for child in hir.walk(node):
            if isinstance(child, hir.ExpressedIdentifier):
                result.update(roots(child.binding_id))
        return result

    captured = set().union(*(roots(binding) for binding in captured)) if captured else set()
    candidates, declarations = set(), {}
    for node in nodes:
        inputs = ()
        scope = node
        if isinstance(node, hir.FunctionCall):
            inputs = [*node.pos_args, *node.kw_args.values()]
        elif isinstance(node, hir.ObjectLiteral):
            inputs = [field.value for field in node.fields]
        elif isinstance(node, hir.ArrayLiteral):
            inputs = node.items
        elif isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign)):
            inputs = [node.value]
        elif isinstance(node, hir.DictStore) and node.value is not None:
            inputs = [node.value]
        elif isinstance(node, hir.Declare):
            inputs = [node.expr]
            if isinstance(node.expr, hir.ExpressedIdentifier):
                declarations[id(node.expr)] = id(node)
        elif isinstance(node, hir.IfArm):
            inputs, scope = [node.body], node.body
        elif isinstance(node, hir.Flow) and node.default is not None:
            inputs, scope = [node.default], node.default
        elif isinstance(node, hir.Block) and resource(node.type) is not None:
            inputs = [item for item in node.items if resource(item.type) is not None]
        # A borrowed sibling argument may still need the source after the
        # callee starts. Do not move a root mentioned elsewhere in this input
        # group, even when its final syntactic occurrence is an owning one.
        counts = {}
        if inputs:
            for child in hir.walk(scope):
                if isinstance(child, hir.ExpressedIdentifier):
                    for root in roots(child.binding_id):
                        counts[root] = counts.get(root, 0) + 1
        for value in inputs:
            while isinstance(value, (hir.ValueCast, hir.RepresentationCast, hir.Obligation)):
                value = value.value if isinstance(value, hir.Obligation) else value.expr
            if (isinstance(value, hir.ExpressedIdentifier) and value.binding_id in owners
                    and resource(value.type) is not None and value.binding_id not in captured
                    and occurrences[id(value)] == 1 and counts.get(value.binding_id) == 1):
                candidates.add(id(value))

    consumes = {}
    def visit(node, after, enabled):
        live = set(after)
        if isinstance(node, hir.ExpressedIdentifier):
            if node.binding_id in enabled and id(node) in candidates and not any(node.binding_id in roots(binding) for binding in live):
                consumes[id(node)] = node.binding_id
            live.add(node.binding_id)
            return live
        if isinstance(node, hir.FunctionLiteral):
            return live | reads(node)
        if isinstance(node, hir.Return):
            return visit(node.item, set(), owners) if node.item is not None else set()
        if isinstance(node, hir.Flow):
            following = visit(node.default, live, enabled) if node.default is not None else live
            for arm in reversed(node.arms):
                if isinstance(arm, hir.LoopArm):
                    # New iteration locals are born again after a backedge;
                    # outer owners are not. Only the former can be consumed
                    # on a repeating path. A return has no backedge at all.
                    born, pending = set(), [arm.body]
                    while pending:
                        child = pending.pop()
                        if isinstance(child, hir.FunctionLiteral):
                            continue
                        if isinstance(child, hir.Declare):
                            born.add(child.binding_id)
                        pending.extend(hir.children(child))
                    repeated = (following | live | reads(arm)) - born
                    visit(arm.body, repeated, enabled & born)
                    following = visit(arm.condition, repeated, set())
                else:
                    taken = visit(arm.body, live, enabled)
                    following = visit(arm.condition, following | taken, enabled)
            return following
        if isinstance(node, hir.Declare):
            live.discard(node.binding_id)
        for child in reversed(tuple(hir.children(node))):
            live = visit(child, live, enabled)
        return live
    visit(body, set(), owners)
    return consumes, declarations
