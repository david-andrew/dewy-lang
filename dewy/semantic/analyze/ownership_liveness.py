"""Path-sensitive last uses for logical resource ownership.

The storage lowerer still decides how bytes travel. This analysis decides
whether a resource may change owners, so cleanup can follow the executed path.
Loop backedges solve a finite liveness fixed point; assignments kill the old
value, so a fresh owner can replace it before the next iteration.
Aliases and captures keep their root live, while returns have no backedge. No traversal order is treated as a branch join.

Liveness is kept per field route, so a component can leave its owner while a
sibling is still read. A live entry is `(binding, path, kind)`: a `read` of
the route, or a `store` into it, which needs the enclosing storage but not
the component's old value.
"""
from .. import hir


def field_route(node):
    """`(binding, field path)` of a route of field reads from a name, else None."""
    path = []
    while isinstance(node, hir.MemberAccess):
        path.append(node.name)
        node = node.value
    if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
        return node.binding_id, tuple(reversed(path))
    return None


def conflicts(path, entry_path, kind):
    """Whether a live entry needs the value a consumption of `path` takes."""
    if kind == 'store':
        # Storing into a component needs its ancestors, not the component.
        return len(path) < len(entry_path) and entry_path[:len(path)] == path
    shared = min(len(path), len(entry_path))
    return path[:shared] == entry_path[:shared]


def conditional_consumptions(body, parameter_owners, resource, component=None):
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
                result.update((root, (), 'read') for root in roots(child.binding_id))
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
            route = field_route(value) if isinstance(value, hir.MemberAccess) and component is not None else None
            if route is not None:
                root = value
                while isinstance(root, hir.MemberAccess):
                    root = root.value
                if (route[0] in owners and route[0] not in captured and occurrences[id(root)] == 1
                        and resource(value.type) is not None and component(value)
                        and counts.get(route[0]) == 1):
                    candidates.add(id(value))

    consumes = {}
    def needed(binding, path, live):
        for entry, entry_path, kind in live:
            if binding in roots(entry) and (entry != binding or conflicts(path, entry_path, kind)):
                return True
        return False

    def consume(node, binding, path, live, enabled):
        if binding in enabled and id(node) in candidates and not needed(binding, path, live):
            consumes[id(node)] = (binding, path)
        else:
            consumes.pop(id(node), None)  # a later fixed-point iteration may reveal a use

    def visit(node, after, enabled, exits=()):
        live = set(after)
        if isinstance(node, hir.ExpressedIdentifier):
            consume(node, node.binding_id, (), live, enabled)
            live.add((node.binding_id, (), 'read'))
            return live
        if isinstance(node, hir.MemberAccess) and (route := field_route(node)) is not None:
            consume(node, route[0], route[1], live, enabled)
            live.add((route[0], route[1], 'read'))
            return live
        if isinstance(node, hir.FunctionLiteral):
            return live | reads(node)
        if isinstance(node, (hir.Break, hir.Continue)) and node.loop_levels < len(exits):
            continuation = exits[-1-node.loop_levels]
            return set(continuation[0 if isinstance(node, hir.Break) else 1])
        if isinstance(node, hir.Return):
            return visit(node.item, set(), owners, exits) if node.item is not None else set()
        if isinstance(node, hir.Flow):
            following = visit(node.default, live, enabled, exits) if node.default is not None else live
            for arm in reversed(node.arms):
                if isinstance(arm, hir.LoopArm):
                    # Solve liveness at the condition, including each continue
                    # edge. Reassignment kills the old value; every path back
                    # to a consuming use must therefore provide a new owner.
                    # The finite entry set only grows, so this terminates.
                    head = set(following)
                    while True:
                        nested = (*exits, (live, head))
                        entering = visit(arm.body, head, enabled, nested)
                        next_head = head | visit(arm.condition, entering | following, enabled, nested)
                        if next_head == head:
                            break
                        head = next_head
                    following = head
                else:
                    taken = visit(arm.body, live, enabled, exits)
                    following = visit(arm.condition, following | taken, enabled, exits)
            return following
        if isinstance(node, hir.Assign) and node.op == '=' and isinstance(node.target, hir.ExpressedIdentifier):
            live = {entry for entry in live if entry[0] != node.target.binding_id}
            return visit(node.value, live, enabled, exits)
        if (isinstance(node, hir.MemberAssign) and isinstance(node.target, hir.MemberAccess)
                and (route := field_route(node.target)) is not None):
            # The old component is dead; the store needs only its ancestors.
            binding, path = route
            live = {entry for entry in live if entry[0] != binding or entry[1][:len(path)] != path}
            live.add((binding, path, 'store'))
            return visit(node.value, live, enabled, exits)
        if isinstance(node, hir.Declare):
            live = {entry for entry in live if entry[0] != node.binding_id}
        for child in reversed(tuple(hir.children(node))):
            live = visit(child, live, enabled, exits)
        return live
    visit(body, set(), owners)
    return consumes, declarations
