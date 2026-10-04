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
from dataclasses import dataclass

from .. import hir, bindings, ty
from . import predicate_effects


def fixed_index(node):
    """The checked slot identity, independent of the selector's spelling."""
    index = node.constant_index
    if index is None and isinstance(node.index, hir.Integer):
        index = node.index.value
    return index if index is not None and index >= 0 else None


@dataclass(frozen=True)
class Selector:
    """An unchanged available scalar binding, never an arbitrary expression."""
    binding: int


def selector_locals(body, inputs):
    """Find once-initialized word locals and where their declarations dominate.

    Repeated declarations are different values on different iterations. They
    keep wildcard identities. Branch/block locals are available only after
    initialization and within that lexical path; a separation check must never
    introduce a read of a later or conditionally uninitialized binding.
    Mutation, place exposure and captures are filtered by liveness separately.
    """
    declarations, before = {}, {}

    def visit(node, visible, repeated=False):
        previous = before.get(id(node))
        before[id(node)] = visible if previous is None else previous & visible
        if isinstance(node, hir.FunctionLiteral):
            return
        if isinstance(node, hir.Block):
            for item in node.items:
                visit(item, visible, repeated)
                if (not repeated and isinstance(item, hir.Declare) and not item.view
                        and item.binding_id is not None
                        and ty.strip_refinement(item.annotation or item.expr.type) == 'int64'):
                    declarations[item.binding_id] = hir.ExpressedIdentifier(
                        item.loc, item.annotation or item.expr.type, item.name, binding_id=item.binding_id)
                    visible = visible | {item.binding_id}
            return
        for child in hir.children(node):
            visit(child, visible, repeated or isinstance(node, hir.LoopArm))

    visit(body, frozenset(inputs))
    return declarations, before


def renew_siblings(live, target, binding, path):
    """After a store to a fixed field path, a later whole read of an ancestor
    reads the new value there. Before the store it needs every other field
    on the way down, but not the replaced component's old value."""
    owners = []
    node = target
    while isinstance(node, hir.MemberAccess):
        owners.append(ty.structural_base(node.value.type))
        node = node.value
    if len(owners) != len(path):
        return live   # an indexed step: keep the whole read
    owners.reverse()
    result = set()
    for entry in live:
        owner, prefix, kind = entry
        if owner != binding or kind != 'read' or len(prefix) >= len(path) or path[:len(prefix)] != prefix:
            result.add(entry)
            continue
        expanded = set()
        for level in range(len(prefix), len(path)):
            record = owners[level]
            if not isinstance(record, ty.ObjectType):
                expanded = None
                break
            expanded.update((binding, path[:level] + (field.name,), 'read') for field in record.fields if field.name != path[level])
        if expanded is None:
            result.add(entry)
        else:
            result |= expanded
    return result


def field_route(node, *, allow_prefix=False, wildcards=False, selectors=frozenset()):
    """A stable route, or conservatively its prefix before an unknown slot."""
    path = []
    while isinstance(node, (hir.MemberAccess, hir.Index)):
        if isinstance(node, hir.MemberAccess):
            path.append(node.name)
            node = node.value
        else:
            index = fixed_index(node)
            if index is None:
                if wildcards:
                    value = node.index
                    path.append(Selector(value.binding_id) if isinstance(value, hir.ExpressedIdentifier)
                                and value.binding_id in selectors else -1)
                elif not allow_prefix:
                    return None
                else:
                    # Cleanup keeps only the containing region; the liveness
                    # footprint above instead retains the selected fields.
                    path.clear()
            else:
                path.append(index)
            node = node.array
    if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
        return node.binding_id, tuple(reversed(path))
    return None


def conflicts(path, entry_path, kind):
    """Whether a live entry needs the value a consumption of `path` takes."""
    shared = min(len(path), len(entry_path))
    pairs = tuple(zip(path[:shared], entry_path[:shared]))
    if any(a != b and not (isinstance(a, (int, Selector)) and isinstance(b, (int, Selector))
                          and (-1 in (a, b) or isinstance(a, Selector) or isinstance(b, Selector))) for a, b in pairs):
        return False
    if kind == 'length':
        return len(path) <= len(entry_path)
    if kind == 'store':
        # A replacement selected through a possibly overlapping array slot
        # cannot renew a known hole. Its old-value cleanup would need the
        # saved selector/presence proof. Replacing a whole containing region
        # (above the wildcard) still starts a new lifetime as before.
        if any(-1 in (a, b) or isinstance(a, Selector) or isinstance(b, Selector) for a, b in pairs):
            return True
        # Storing into a component needs its ancestors, not the component.
        return len(path) < len(entry_path)
    return True


def conditional_consumptions(body, parameter_owners, resource, component=None, *, call_writes=None, read_only_places=frozenset(), selector_inputs=frozenset(), selector_scopes=None, move_only=lambda node: False, outliving=frozenset()):
    """Owning inputs whose value is not read again on any path.

    `outliving` names place parameters: their components may transfer, and
    the caller reads each one whole when the function returns."""
    nodes, owners, aliases, captured, occurrences = [], set(), {}, set(), {}
    owners.update(p.binding_id for p in parameter_owners)
    owners.update(outliving)
    exit_live = frozenset((binding, (), 'read') for binding in outliving)
    required_views, view_conflicts = {}, {}
    def storage_route(node):
        path = bindings.access_path(node, dictionaries=True)
        prefix = []
        for step in path.steps:
            if not isinstance(step, hir.MemberAccess):
                break  # resizing/detachment can relocate any indexed slot
            prefix.append(step.name)
        return path.binding_id, tuple(prefix)

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
            if not node.view:
                owners.add(node.binding_id)
            else:
                required_views[node.binding_id] = (node, storage_route(node.expr))
            source = bindings.access_path(node.expr, dictionaries=True).root if node.view else node.expr
            if isinstance(source, hir.ExpressedIdentifier):
                aliases[node.binding_id] = source.binding_id
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

    def disjoint_inputs(scope, selected, route):
        """Other operands may use siblings, but cannot observe a moved field.

        Walk maximal routes instead of their identifier leaves. Aliases keep
        their conservative whole-root footprint; selector expressions remain
        reads even when the selected storage itself is disjoint.
        """
        pending = [scope]
        while pending:
            child = pending.pop()
            if child is selected:
                continue
            access = field_route(child, wildcards=True)
            if access is not None:
                if route[0] in roots(access[0]) and (access[0] != route[0]
                        or conflicts(route[1], access[1], 'read')):
                    return False
                while isinstance(child, (hir.MemberAccess, hir.Index)):
                    if isinstance(child, hir.Index):
                        pending.append(child.index)
                        child = child.array
                    else:
                        child = child.value
            else:
                pending.extend(hir.children(child))
        return True

    captured = set().union(*(roots(binding) for binding in captured)) if captured else set()
    # Inputs exist at every use in this function. Do not manufacture reads of
    # a later local, a changing loop selector, an exposed place or a capture.
    selectors = set(selector_inputs) - captured - predicate_effects.mutated_bindings(body, call_writes=call_writes)
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
        # A borrowed argument may still need the source after the callee
        # starts. Whole-root transfers require a unique read; component
        # transfers can also prove the remaining operands disjoint below.
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
            route = field_route(value, allow_prefix=True) if isinstance(value, (hir.MemberAccess, hir.Index)) and component is not None else None
            if route is not None:
                root = value
                while isinstance(root, (hir.MemberAccess, hir.Index)):
                    root = root.value if isinstance(root, hir.MemberAccess) else root.array
                # Selector reads happen before this component transfers.
                # Overlapping operands prevent a same-expression donation;
                # the backward walk checks the selector's own dependencies.
                own_reads = sum(route[0] in roots(child.binding_id) for child in hir.walk(value)
                                if isinstance(child, hir.ExpressedIdentifier))
                if (route[0] in owners and route[0] not in captured and occurrences[id(root)] == 1
                        and resource(value.type) is not None and component(value)
                        and (counts.get(route[0]) == own_reads or disjoint_inputs(scope, value, route))):
                    candidates.add(id(value))

    consumes, obligations = {}, {}
    def needed(binding, path, live, propose, available):
        clauses = []
        for entry, entry_path, kind in live:
            if binding in roots(entry) and (entry != binding or conflicts(path, entry_path, kind)):
                alternatives = []
                if propose and entry == binding and kind != 'store':
                    for left, right in zip(path, entry_path):
                        if (left != right and -1 not in (left, right)
                                and isinstance(left, (int, Selector)) and isinstance(right, (int, Selector))
                                and (isinstance(left, Selector) or isinstance(right, Selector))):
                            if all(not isinstance(term, Selector) or term.binding in available for term in (left, right)):
                                alternatives.append((left, right))
                if not alternatives:
                    return None
                clauses.append(alternatives)
        return clauses

    def consume(node, binding, path, live, enabled, *, stored_path=None):
        available = selector_inputs if selector_scopes is None else selector_scopes.get(id(node), frozenset())
        clauses = needed(binding, path, live, move_only(node), available) if binding in enabled and id(node) in candidates else None
        if clauses is not None:
            consumes[id(node)] = (binding, path if stored_path is None else stored_path)
            obligations[id(node)] = clauses
        else:
            consumes.pop(id(node), None)  # a later fixed-point iteration may reveal a use
            obligations.pop(id(node), None)

    def visit_selectors(node, live, enabled, exits):
        # A known result does not erase evaluation. Work backwards through
        # selectors without turning the selected storage into a whole read.
        while isinstance(node, (hir.MemberAccess, hir.Index)):
            if isinstance(node, hir.Index):
                live = visit(node.index, live, enabled, exits)
                node = node.array
            else:
                node = node.value
        return live

    def visit(node, after, enabled, exits=()):
        live = set(after)
        # Logical borrows are source contracts, even in an unused function.
        # Check writes against aliases live on this path before lowering or
        # reachability can hide the conflict. Physical placement checks remain
        # with the common view proof in lowering.
        changed = []
        target = predicate_effects.write_target(node)
        if isinstance(node, hir.Place) and id(node) in read_only_places:
            target = None
        if isinstance(node, (hir.DictStore, hir.DictRemove)) and isinstance(target, hir.MemberAccess):
            target = target.value
        if target is not None:
            changed.append(storage_route(target))
        if isinstance(node, hir.FunctionCall) and call_writes:
            changed.extend((binding, ()) for binding in call_writes.get(id(node), ()))
        if changed:
            for entry, _, _ in live:
                for alias in roots(entry) & required_views.keys():
                    declaration, (owner, prefix) = required_views[alias]
                    for changed_owner, changed_path in changed:
                        if changed_owner is not None and owner in roots(changed_owner) and conflicts(prefix, changed_path, 'read'):
                            view_conflicts[id(node)] = (node, declaration)
        if isinstance(node, hir.ExpressedIdentifier):
            consume(node, node.binding_id, (), live, enabled)
            live.add((node.binding_id, (), 'read'))
            return live
        if isinstance(node, (hir.MemberAccess, hir.Index)) and (route := field_route(node, wildcards=True, selectors=selectors)) is not None:
            # A wildcard retains fields below an unknown selector. Thus
            # rows[i].left and rows[j].right are disjoint for every i and j,
            # while two .left routes still conflict. Cleanup stores only the
            # static containing region and captures actual selectors once.
            region = field_route(node, allow_prefix=True)
            consume(node, route[0], route[1], live, enabled, stored_path=region[1])
            live.add((route[0], route[1], 'read'))
            return visit_selectors(node, live, enabled, exits)
        if isinstance(node, hir.ArrayLength) and (route := field_route(node.array, wildcards=True, selectors=selectors)) is not None:
            live.add((route[0], route[1], 'length'))
            return visit_selectors(node.array, live, enabled, exits)
        if isinstance(node, hir.FunctionLiteral):
            return live | reads(node)
        if isinstance(node, (hir.Break, hir.Continue)) and node.loop_levels < len(exits):
            continuation = exits[-1-node.loop_levels]
            return set(continuation[0 if isinstance(node, hir.Break) else 1])
        if isinstance(node, hir.Return):
            return visit(node.item, set(exit_live), owners, exits) if node.item is not None else set(exit_live)
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
        if (isinstance(node, (hir.MemberAssign, hir.IndexAssign)) and isinstance(node.target, (hir.MemberAccess, hir.Index))
                and (route := field_route(node.target, wildcards=True, selectors=selectors)) is not None):
            # The old component is dead; the store needs only its ancestors.
            binding, path = route
            if not any(step == -1 or isinstance(step, Selector) for step in path):
                live = {entry for entry in live if entry[0] != binding or entry[1][:len(path)] != path}
                live = renew_siblings(live, node.target, binding, path)
            live.add((binding, path, 'store'))
            return visit_selectors(node.target, visit(node.value, live, enabled, exits), enabled, exits)
        if isinstance(node, hir.Declare):
            live = {entry for entry in live if entry[0] != node.binding_id}
        for child in reversed(tuple(hir.children(node))):
            live = visit(child, live, enabled, exits)
        return live
    visit(body, set(exit_live), owners)
    return consumes, declarations, tuple(view_conflicts.values()), obligations
