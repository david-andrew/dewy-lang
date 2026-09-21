"""Scope borrows: which locals may alias storage they read instead of copying it.

A port of the native compiler's `backend/udewy/borrowing.dewy` (and the
`writes` part of `captures.dewy`). The rules are kept identical so both
compilers make the same borrow decisions:

- a binding is *stable* in its function when nothing writes it (`write_targets`
  roots), it is not a place parameter, a global, captured by a nested
  function, or exposed to raw memory operations, syscalls, aggregate
  transmutes or unknown callees within its own function;
- a *route* is the binding and outside-in field path an expression reads;
  an index step forgets the fields above it (unknown indices may alias);
- an owner is stable for a route when the owner binding is stable, or it is a
  tracked parameter none of whose mutated, rebound or escaping routes overlap
  the borrowed route;
- an `Index` whose index expression may write the array it reads is an
  *array snapshot*: the receiver is copied before indexing and the read
  never borrows.

Transitive writes to globals and captured owners use the shared effect call
graph. The native pass additionally proves stability for more place
parameters; this port remains conservative there and borrows a subset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...semantic import hir, ty
from ...semantic.analyze.effects import INDEX_STEP, ParameterEffects, ProgramEffects, analyze_global_writes

# The operator spellings µDewy emits directly (emit.py's binop/prefix tables);
# listed here to avoid a circular import with the emitter.
PURE_OPERATORS = {
    '__add__', '__sub__', '__mul__', '__floordiv__', '__mod__', '__lshift__', '__rshift__',
    '__eq__', '__ne__', '__gt__', '__lt__', '__ge__', '__le__', '__and__', '__or__', '__xor__',
    '__nand__', '__nor__', '__xnor__', '__unary_sub__', '__not__', '__dewy_raw_lshift__', '__dewy_raw_rshift__',
}


@dataclass(frozen=True)
class Route:
    binding: int
    fields: tuple[str, ...]


@dataclass
class Function:
    literal: hir.FunctionLiteral
    locals: set[int] = field(default_factory=set)
    writes: set[int] = field(default_factory=set)
    places: set[int] = field(default_factory=set)


@dataclass
class Plan:
    functions: dict[int, Function] = field(default_factory=dict)      # id(literal) -> Function
    globals: set[int] = field(default_factory=set)
    named: dict[int, hir.FunctionLiteral] = field(default_factory=dict)   # binding id -> literal it names
    exposed_bindings: set[int] = field(default_factory=set)
    stable_bindings: set[int] = field(default_factory=set)
    stable_parameters: dict[int, ParameterEffects] = field(default_factory=dict)
    array_snapshots: set[int] = field(default_factory=set)             # id(Index) whose index may write the array
    ambient_writes: dict[int, set[int]] = field(default_factory=dict)  # call identity -> nonlocal owners written
    scoped_views: set[int] = field(default_factory=set)                # view binding -> interval/lexical proof
    view_scopes: dict[int, hir.Block] = field(default_factory=dict)
    view_regions: dict[int, list[hir.AST]] = field(default_factory=dict)


def unwrap(node: hir.AST) -> hir.AST:
    """Look through the wrappers that do not change what storage is read."""
    while True:
        if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            node = node.items[0]
        elif isinstance(node, hir.Obligation):
            node = node.value
        elif isinstance(node, hir.Suppress):
            node = node.item
        else:
            return node


def route(node: hir.AST) -> Route | None:
    """The binding and outside-in field path an expression reads, or None."""
    fields: list[str] = []
    while True:
        node = unwrap(node)
        if isinstance(node, hir.MemberAccess):
            fields.append(node.name)
            node = node.value
        elif isinstance(node, hir.Index):
            fields = []   # an unknown index may alias any element: only the fields above it distinguish storage
            node = node.array
        elif isinstance(node, hir.DictLookup):
            fields = []   # a dictionary value lives in the dictionary's value array
            node = node.values
        elif isinstance(node, hir.ExpressedIdentifier):
            if node.binding_id is None:
                return None
            return Route(node.binding_id, tuple(reversed(fields)))
        else:
            return None


def overlap(a: Route, b: Route) -> bool:
    if a.binding != b.binding:
        return False
    return all(x == y for x, y in zip(a.fields, b.fields))


def root_binding(node: hir.AST) -> int | None:
    node = unwrap(node)
    if isinstance(node, hir.ExpressedIdentifier):
        return node.binding_id
    if isinstance(node, hir.MemberAccess):
        return root_binding(node.value)
    if isinstance(node, hir.Index):
        return root_binding(node.array)
    if isinstance(node, hir.DictLookup):
        return root_binding(node.values)
    if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
        return root_binding(node.expr)
    return None


def write_targets(node: hir.AST) -> list[hir.AST]:
    """The expressions a node writes (captures.dewy `write_targets`)."""
    if isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign, hir.Place, hir.IteratorExpression)):
        return [node.target]
    if isinstance(node, (hir.DictStore, hir.DictRemove)):
        targets = [node.keys]
        if node.values is not None:
            targets.append(node.values)
        return targets
    if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod) and node.func.name != 'join':
        return [node.func.array]
    return []


def children(node: object):
    """The direct HIR children of a node, in field order."""
    if isinstance(node, hir.AST):
        from dataclasses import fields as dataclass_fields
        for field_ in dataclass_fields(node):
            value = getattr(node, field_.name)
            for child in (value if isinstance(value, (list, tuple)) else [value]):
                if isinstance(child, hir.AST):
                    yield child
                elif isinstance(child, hir.ObjectField):
                    yield child.value
                elif isinstance(child, dict):
                    for item in child.values():
                        if isinstance(item, hir.AST):
                            yield item
    elif isinstance(node, (hir.Param, hir.BoundParam)):
        if isinstance(node, hir.BoundParam):
            yield node.value


def literal_params(literal: hir.FunctionLiteral) -> list[hir.Param]:
    params = [*literal.pos_or_kw_args, *literal.kw_only_args]
    if literal.rest_args is not None:
        params.append(literal.rest_args)
    return params


def _walk_function(literal: hir.FunctionLiteral):
    """Every node of a function's own body and defaults, not entering nested literals."""
    stack: list[object] = [literal.body]
    for param in literal_params(literal):
        if isinstance(param, hir.BoundParam):
            stack.append(param.value)
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in seen or not isinstance(node, hir.AST):
            continue
        seen.add(id(node))
        yield node
        if isinstance(node, (hir.FunctionLiteral, hir.GenericFunction)):
            continue
        stack.extend(children(node))


WORD_PRIMITIVES = {'int', 'uint', 'int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64', 'float32', 'float64', 'bool', 'true', 'false', 'none'}


def _word_value(type_: ty.Type) -> bool:
    """A value that fits one machine word: exposing it exposes no storage (borrowing.dewy `word_value`)."""
    plain = ty.unfold(ty.strip_refinement(type_))
    if isinstance(plain, ty.IntegerLiteralType):
        return -9223372036854775808 <= plain.value <= 18446744073709551615
    return isinstance(plain, str) and plain in WORD_PRIMITIVES


def is_raw_call(node: hir.FunctionCall, plan: Plan, source_bindings: set[int]) -> bool:
    """A call that may expose an aggregate argument's storage (borrowing.dewy `raw`)."""
    callee = node.func
    if isinstance(callee, hir.ExpressedIdentifier):
        if callee.binding_id is not None and callee.binding_id in plan.named:
            return False
        name = callee.name
        memory = name.startswith('__load_') or name.startswith('__store_')
        unknown = (callee.binding_id is not None and callee.binding_id in source_bindings) or not (
            name in PURE_OPERATORS or (name.startswith('__') and name.endswith('__'))
        )
        return memory or unknown or name.startswith('__syscall')
    if isinstance(callee, hir.ArrayMethod):
        return callee.name == 'sort' and 'key' in node.kw_args
    if isinstance(callee, hir.FunctionLiteral):
        return False
    return not (isinstance(callee, hir.BoundMethod))


def exposed_roots(plan: Plan, source_bindings: set[int]) -> set[int]:
    """Bindings whose storage address may reach raw operations within their own function."""
    exposed: set[int] = set()

    def expose(node: hir.AST) -> None:
        if _word_value(node.type):
            return
        binding = root_binding(node)
        if binding is not None:
            exposed.add(binding)

    for function in plan.functions.values():
        for node in _walk_function(function.literal):
            if isinstance(node, hir.Assert):
                continue   # a failed assertion only formats its message
            if isinstance(node, hir.Transmute):
                if not (_word_value(node.type) and _word_value(node.expr.type)):
                    expose(node.expr)
            elif isinstance(node, hir.FunctionCall) and is_raw_call(node, plan, source_bindings):
                for argument in [*node.pos_args, *node.kw_args.values()]:
                    expose(argument.target if isinstance(argument, hir.Place) else argument)
                if isinstance(node.func, hir.ArrayMethod):
                    expose(node.func.array)
    return exposed


def expression_conflicts(root: hir.AST, source: Route | None, plan: Plan, source_bindings: set[int]) -> bool:
    """Whether evaluating `root` may write or alias the `source` route (conservative)."""
    for node in _walk_function_subtree(root):
        if isinstance(node, hir.FunctionCall):
            if source is not None and source.binding in plan.ambient_writes.get(id(node), ()):
                return True
            callee = node.func
            if isinstance(callee, hir.ExpressedIdentifier) and callee.binding_id in plan.named:
                writes = plan.functions[id(plan.named[callee.binding_id])].writes
                if source is None or source.binding in writes:
                    return True
                # Place arguments are examined below while walking the call's
                # children; ambient writes were checked through the call graph.
                continue
            pure = isinstance(callee, hir.ExpressedIdentifier) and (callee.binding_id is None or callee.binding_id not in source_bindings) and callee.name in PURE_OPERATORS
            if isinstance(callee, hir.ArrayMethod):
                if callee.name == 'sort' and 'key' in node.kw_args:
                    return True
            elif not pure:
                return True
        for target in write_targets(node):
            exposed = route(target)
            if source is None or exposed is None or overlap(source, exposed):
                return True
    return False


def _walk_function_subtree(root: hir.AST):
    stack: list[object] = [root]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in seen or not isinstance(node, hir.AST):
            continue
        seen.add(id(node))
        yield node
        if isinstance(node, (hir.FunctionLiteral, hir.GenericFunction)):
            continue
        stack.extend(children(node))


@dataclass
class ViewScope:
    items: list[hir.AST]
    references: list[set[int]]
    locals: set[int]
    dependents: dict[int, set[int]]
    starts: dict[int, int]
    ends: dict[int, int]


def prepare_view_scope(scope: hir.Block) -> ViewScope:
    """Collect alias dependencies once for all candidate views in a block."""
    statements = [list(_walk_function_subtree(item)) for item in scope.items]
    references = [{node.binding_id for node in nodes if isinstance(node, hir.ExpressedIdentifier)
                   and node.binding_id is not None} for nodes in statements]
    locals_ = set()
    dependents: dict[int, set[int]] = {}
    starts, ends = {}, {}
    for index, nodes in enumerate(statements):
        for node in nodes:
            target = value = None
            if isinstance(node, hir.Declare):
                starts.setdefault(id(node), index)
                ends[id(node)] = index
                locals_.add(node.binding_id)
                if node.view or not _word_value(node.expr.type):
                    target, value = node.binding_id, node.expr
            elif isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign)) and not _word_value(node.value.type):
                target, value = root_binding(node.target), node.value
            if target is not None and value is not None:
                pending_values = [value]
                while pending_values:
                    read = pending_values.pop()
                    if isinstance(read, (hir.CopyValue, hir.FunctionLiteral, hir.GenericFunction)):
                        continue  # an explicit snapshot owns independent storage
                    if isinstance(read, hir.ExpressedIdentifier) and read.binding_id is not None:
                        dependents.setdefault(read.binding_id, set()).add(target)
                    pending_values.extend(hir.children(read))
    return ViewScope(scope.items, references, locals_, dependents, starts, ends)


def view_conflicts(region: list[hir.AST], aliases: set[int], source: Route, plan: Plan, source_bindings: set[int], *, retained: bool = False) -> bool:
    """Backward liveness within the statement interval, including exit edges.

    A return ends the view's lifetime on that path. Writes after its last
    read (notably implicit drop calls) cannot affect it. Loops conservatively
    keep every referenced alias live across the backedge.
    """
    def reads(node):
        return any(isinstance(child, hir.ExpressedIdentifier) and child.binding_id in aliases
                   for child in _walk_function_subtree(node))

    def visit(node, live):
        if isinstance(node, hir.Return):
            return visit(node.item, retained) if node.item is not None else (False, retained)
        if isinstance(node, hir.Block):
            conflict = False
            for item in reversed(node.items):
                bad, live = visit(item, live)
                conflict |= bad
            return conflict, live
        if isinstance(node, hir.Flow):
            conflict, remaining = visit(node.default, live) if node.default is not None else (False, live)
            for arm in reversed(node.arms):
                after = live or isinstance(arm, hir.LoopArm) and (reads(arm.condition) or reads(arm.body))
                bad, before = visit(arm.body, after)
                condition_bad, remaining = visit(arm.condition, before or remaining)
                conflict |= bad or condition_bad
            return conflict, remaining
        before = live or reads(node)
        return before and expression_conflicts(node, source, plan, source_bindings), before

    conflict, live = False, retained
    for item in reversed(region):
        bad, live = visit(item, live)
        conflict |= bad
    return conflict


def view_region(scope: ViewScope, declaration: hir.Declare, excluded: set[int]) -> list[hir.AST]:
    """End after every derived alias's last use; keep control flow indivisible.

    Aggregate forwarding conservatively creates a dependency even when later
    lowering chooses a copy. Captured, exposed and outward-stored aliases
    retain the lexical lifetime.
    """
    start = scope.starts.get(id(declaration))
    if start is None:
        return scope.items
    live = {declaration.binding_id}
    pending = list(live)
    while pending:
        for target in scope.dependents.get(pending.pop(), ()):
            if target not in live:
                live.add(target)
                pending.append(target)
    if live & excluded or not live <= scope.locals:
        return scope.items
    stop = max((index for index, reads in enumerate(scope.references) if reads & live), default=start)
    return scope.items[start:max(scope.ends[id(declaration)], stop) + 1]


def analyze(root: hir.Block, captured: set[int], effects: ProgramEffects, source_bindings: set[int]) -> Plan:
    """Compute the borrow plan for a module (borrowing.dewy `details`, the scope-borrow part)."""
    plan = Plan()
    # globals: top-level declarations, through unscoped blocks
    pending: list[hir.AST] = list(root.items)
    while pending:
        item = pending.pop()
        if isinstance(item, hir.Declare) and item.binding_id is not None:
            plan.globals.add(item.binding_id)
        elif isinstance(item, hir.Block) and not item.scoped:
            pending.extend(item.items)
    # functions
    def discover(node: object) -> None:
        stack: list[object] = [node]
        seen: set[int] = set()
        while stack:
            current = stack.pop()
            if id(current) in seen or not isinstance(current, hir.AST):
                continue
            seen.add(id(current))
            if isinstance(current, hir.Declare) and isinstance(unwrap(current.expr), hir.FunctionLiteral) and current.binding_id is not None:
                plan.named[current.binding_id] = unwrap(current.expr)
            if isinstance(current, hir.FunctionLiteral):
                function = Function(current)
                plan.functions[id(current)] = function
                for param in literal_params(current):
                    if param.binding_id is not None:
                        function.locals.add(param.binding_id)
                        if param.place:
                            function.places.add(param.binding_id)
                for inner in _walk_function(current):
                    if isinstance(inner, hir.Declare) and inner.binding_id is not None:
                        function.locals.add(inner.binding_id)
                    if isinstance(inner, hir.IteratorExpression) and inner.target.binding_id is not None:
                        function.locals.add(inner.target.binding_id)
                    for target in write_targets(inner):
                        binding = root_binding(target)
                        if binding is not None:
                            function.writes.add(binding)
            stack.extend(children(current))
    discover(root)
    places: set[int] = set()
    for function in plan.functions.values():
        places |= function.places
    exposed = exposed_roots(plan, source_bindings)
    plan.exposed_bindings = exposed
    for function in plan.functions.values():
        for binding in function.locals:
            if binding not in function.writes and binding not in places and binding not in plan.globals and binding not in captured and binding not in exposed:
                plan.stable_bindings.add(binding)
        for param in literal_params(function.literal):
            binding = param.binding_id
            if binding is None or binding in captured or binding in plan.globals or binding in exposed or param.place:
                continue   # place parameters need the ambient graph the native pass has
            summary = effects.for_param_binding(binding)
            if summary is not None:
                plan.stable_parameters[binding] = summary
    plan.ambient_writes = analyze_global_writes(root, (plan.globals | captured) - plan.named.keys())
    # A nonescaping place call only lends its owner for that call. It must
    # conflict while a view is live, but need not lengthen the view past its
    # last use. Unknown or retaining calls keep the whole-scope exclusion.
    safe_places, unsafe_places = set(), set()
    for function in plan.functions.values():
        for node in _walk_function(function.literal):
            if not isinstance(node, hir.FunctionCall):
                continue
            target = (node.func if isinstance(node.func, hir.FunctionLiteral) else
                      plan.named.get(node.func.binding_id) if isinstance(node.func, hir.ExpressedIdentifier) else None)
            if target is None:
                unsafe_places.update(id(arg) for arg in [*node.pos_args, *node.kw_args.values()] if isinstance(arg, hir.Place))
                continue
            for index, param in enumerate(literal_params(target)):
                arg = node.pos_args[index] if index < len(node.pos_args) else node.kw_args.get(param.name)
                if not param.place or not isinstance(arg, hir.Place):
                    continue
                summary = effects.for_param_binding(param.binding_id)
                if summary is not None and not summary.escapes:
                    safe_places.add(id(arg))
                else:
                    unsafe_places.add(id(arg))
    safe_places -= unsafe_places
    excluded_owners = captured | exposed | places
    for function in plan.functions.values():
        view_candidates = set()
        for node in _walk_function(function.literal):
            if isinstance(node, hir.Declare) and node.binding_id is not None:
                source = route(node.expr)
                inferred = (not _word_value(node.expr.type)
                            and isinstance(unwrap(node.expr), (hir.Index, hir.MemberAccess, hir.DictLookup))
                            and node.binding_id in plan.stable_bindings and source is not None
                            and source.binding in function.locals and source.binding not in excluded_owners
                            and not stable_owner(source, plan))
                if node.view or inferred:
                    view_candidates.add(node.binding_id)
            if isinstance(node, hir.Place) and id(node) not in safe_places and (addressed := root_binding(node.target)) is not None:
                excluded_owners.add(addressed)
            if isinstance(node, (hir.Index, hir.StringIndex)):
                source = route(node.array if isinstance(node, hir.Index) else node.string)
                if source is not None and source.binding in places:
                    source = None
                if expression_conflicts(node.index, source, plan, source_bindings):
                    plan.array_snapshots.add(id(node))
            elif isinstance(node, hir.DictLookup):
                source = route(node.values)
                if source is not None and source.binding in places:
                    source = None
                if expression_conflicts(node.key, source, plan, source_bindings):
                    plan.array_snapshots.add(id(node))
        # An unwritten let is as read-only as a const for this proof. Only
        # private owners that failed the whole-function proof need a scan. Share its dependency graph across each block's views.
        if not view_candidates:
            continue
        pending = [(function.literal.body, None)]
        seen = set()
        candidates = {}
        while pending:
            node, scope = pending.pop()
            key = (id(node), id(scope))
            if key in seen or isinstance(node, hir.FunctionLiteral):
                continue
            seen.add(key)
            if isinstance(node, hir.Block) and node.scoped:
                scope = node
            if isinstance(node, hir.Declare) and node.binding_id in view_candidates and scope is not None:
                candidates.setdefault(node.binding_id, []).append((node, scope))
            pending.extend((child, scope) for child in hir.children(node))
        prepared_scopes = {}
        for binding, uses in candidates.items():
            plan.view_scopes[binding] = uses[0][1]
            regions = []
            safe = True
            for node, scope in uses:
                source = route(node.expr)
                if id(scope) not in prepared_scopes:
                    prepared_scopes[id(scope)] = prepare_view_scope(scope)
                region = view_region(prepared_scopes[id(scope)], node, excluded_owners)
                regions.extend(region)
                aliases = {binding}
                pending_aliases = [binding]
                while pending_aliases:
                    for dependent in prepared_scopes[id(scope)].dependents.get(pending_aliases.pop(), ()):
                        if dependent not in aliases:
                            aliases.add(dependent)
                            pending_aliases.append(dependent)
                if (source is None or source.binding not in function.locals
                        or source.binding in excluded_owners
                        or view_conflicts(region, aliases, source, plan, source_bindings,
                                          retained=bool(aliases & excluded_owners) or not aliases <= prepared_scopes[id(scope)].locals)):
                    safe = False
            plan.view_regions[binding] = regions
            if safe:
                plan.scoped_views.add(binding)
    return plan


def stable_owner(source: Route, plan: Plan) -> bool:
    """The route's storage is not written, rebound or exposed while its function runs."""
    if source.binding in plan.stable_bindings:
        return True
    summary = plan.stable_parameters.get(source.binding)
    if summary is None:
        return False
    for change in (*summary.mutates, *summary.rebinds, *summary.escapes):
        if overlap(source, Route(source.binding, tuple(step for step in change))):
            return False
    return True
