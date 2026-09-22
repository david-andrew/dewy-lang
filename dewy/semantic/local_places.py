"""Resolve checked local places to rooted storage routes before fact analysis.

Selectors are captured once; writes still pass through normal mutable-place
lowering, including COW detachment. No raw pointer survives between uses.
The source declaration remains available for diagnostics and lifetime checks.
"""
from dataclasses import replace, fields, is_dataclass

from . import hir, ty, bindings, builtins
from .errors import user_error
from ..reporting import Pointer
from ..parser import t0


def mutable(declaration):
    return isinstance(declaration, hir.Declare) and declaration.view and declaration.decltype not in {'const', 'local_const'}


def prepare(root, registry, srcfile):
    aliases = {node.binding_id: node for node in hir.walk(root) if mutable(node)}
    if not aliases:
        return root
    from ..backend.udewy import borrowing
    from .analyze.effects import analyze_effects
    captured = set()
    scopes = {}
    def discover(node, scope=None, enclosing=frozenset()):
        if isinstance(node, hir.FunctionLiteral):
            references = {read.binding_id for read in hir.walk(node.body) if isinstance(read, hir.ExpressedIdentifier)}
            captured.update(references & enclosing)
            scope = None
            enclosing = enclosing | {child.binding_id for child in borrowing._walk_function_subtree(node.body) if isinstance(child, hir.Declare)}
        if isinstance(node, hir.Block):
            scope = node
        if mutable(node):
            scopes[node.binding_id] = scope
        for child in hir.children(node):
            discover(child, scope, enclosing)
    discover(root)
    plan = borrowing.analyze(root, captured, analyze_effects(root), set(registry.by_id))
    for binding, declaration in aliases.items():
        source = borrowing.route(declaration.expr)
        while source is not None and source.binding in aliases:
            parent = borrowing.route(aliases[source.binding].expr)
            source = None if parent is None else borrowing.Route(parent.binding, parent.fields + source.fields)
        scope = scopes[binding]
        if source is None or scope is None or binding in captured or source.binding in (plan.exposed_bindings | captured):
            user_error(srcfile, 'cannot prove mutable local place lifetime', Pointer(span=declaration.loc, message='the selected owner must remain available through the place’s last use'))
        prepared = borrowing.prepare_view_scope(scope)
        region = borrowing.view_region(prepared, declaration, captured)
        # Borrowing through the alias itself is the requested write-through
        # operation. Ancestor writes and unknown calls still fence its source.
        live = {binding}
        pending = [binding]
        while pending:
            for dependent in prepared.dependents.get(pending.pop(), ()):
                if dependent not in live:
                    live.add(dependent)
                    pending.append(dependent)
        if borrowing.view_conflicts(region, live, source, plan, set(registry.by_id)):
            user_error(srcfile, 'mutable local place conflicts with its owner', Pointer(span=declaration.loc, message='the selected owner must remain available through the place’s last use'))

    routes = {}
    replacements = {}
    def capture(value, prefix):
        binding = registry.allocate(object(), f'__place_index_{registry.next_id}', 'value', value.loc)
        binding.type = value.type
        declaration = hir.Declare(value.loc, ty.VOID_TYPE, 'const', binding.name, value.type, value, binding_id=binding.id)
        binding.declaration = declaration
        prefix.append(declaration)
        return hir.ExpressedIdentifier(value.loc, value.type, binding.name, binding_id=binding.id)

    def freeze(value, prefix):
        value = borrowing.unwrap(value)
        if isinstance(value, hir.ExpressedIdentifier):
            return routes.get(value.binding_id, value)
        if isinstance(value, hir.MemberAccess):
            return replace(value, value=freeze(value.value, prefix))
        if isinstance(value, hir.DictLookup) and value.proven:
            # Membership was checked at the declaration. The lifetime proof
            # prevents entry replacement/removal while the place is live.
            # Reprobe by the saved key: copies may compact dictionary storage.
            keys = freeze(value.keys, prefix)
            values = replace(value.values, value=keys.value)
            key = value.key if isinstance(value.key, (hir.Integer, hir.String)) else capture(value.key, prefix)
            return replace(value, keys=keys, values=values, key=key, position=None, static_position=None)
        if isinstance(value, hir.Index):
            array = freeze(value.array, prefix)
            index = value.index if isinstance(value.index, hir.Integer) else capture(value.index, prefix)
            # Forming a place owes the selection proof here even if it is
            # never read. These ordinary checked assertions erase after proof;
            # no temporary copy of the selected value is introduced.
            zero = hir.Integer(value.loc, 'int64', t0.base10, 0)
            length = hir.ArrayLength(value.loc, 'int64', array)
            for name, left, right in [('__ge__', index, zero), ('__lt__', index, length)]:
                signature = ty.FunctionType([ty.PosOrKwArg(None, left.type), ty.PosOrKwArg(None, right.type)], [], None, 'bool')
                comparison = hir.FunctionCall(value.loc, 'bool', hir.ExpressedIdentifier(value.loc, signature, name), [left, right], {})
                prefix.append(hir.Assert(value.loc, ty.VOID_TYPE, comparison, 'local place selector is within its owner'))
            return replace(value, array=array, index=index)
        user_error(srcfile, 'unsupported local place selection', Pointer(span=value.loc, message='select a named variable, field, array element, or proven dictionary entry'))

    # Traversal order is lexical declaration order. Binding ids, rather than
    # names, distinguish shadowed declarations and dependent aliases.
    for node in hir.walk(root):
        if mutable(node):
            prefix = []
            routes[node.binding_id] = freeze(node.expr, prefix)
            replacements[id(node)] = hir.Block(node.loc, ty.VOID_TYPE, prefix, False)

    terms = {binding: bindings.array_route_id(route, registry) for binding, route in routes.items()}
    # Facts about projected aliases must name the same route as direct owner
    # reads. Preserve selector dependencies so loop reentry invalidates them.
    for binding, route in routes.items():
        canonical = terms[binding]
        if canonical is None:
            continue
        owner = registry.by_id[canonical].route_root or canonical
        prefix = registry.route_paths.get(canonical, ())
        for old in registry.routes_under(binding):
            metadata = registry.by_id[old]
            new = registry.route_id(owner, prefix + registry.route_paths[old], metadata.type, metadata.loc)
            terms[old] = new
            for dependent in registry.index_routes.values():
                if canonical in dependent or old in dependent:
                    dependent.add(new)

    memo = {}
    def map_type(value):
        # Named recursive references keep their nominal identity. Their target
        # is owned by its declaration, not cloned as part of a local route.
        if isinstance(value, ty.NamedType):
            return value
        if not is_dataclass(value) or type(value).__module__ != ty.__name__:
            return value
        if id(value) in memo:
            return memo[id(value)]
        changes = {}
        for field in fields(value):
            old = getattr(value, field.name)
            new = mapped(old)
            if isinstance(value, ty.Proposition) and field.name in {'term_id', 'subject_id'}:
                new = terms.get(old, old)
            if new is not old:
                changes[field.name] = new
        result = replace(value, **changes) if changes else value
        memo[id(value)] = result
        return result

    def mapped(value):
        if isinstance(value, hir.AST):
            return visit(value)
        if isinstance(value, (list, tuple)):
            items = [mapped(child) for child in value]
            return value if all(a is b for a, b in zip(value, items)) else type(value)(items)
        if isinstance(value, dict):
            items = {key: mapped(child) for key, child in value.items()}
            return value if all(value[key] is child for key, child in items.items()) else items
        if isinstance(value, (hir.ObjectField, hir.Param)):
            return replace(value, **{field.name: mapped(getattr(value, field.name)) for field in fields(value)})
        return map_type(value)

    def visit(node):
        if id(node) in replacements:
            return visit(replacements[id(node)])
        if isinstance(node, hir.ExpressedIdentifier) and node.binding_id in routes:
            return replace(routes[node.binding_id], loc=node.loc, type=map_type(node.type))
        if isinstance(node, hir.Assign) and node.target.binding_id in routes:
            target = visit(node.target)
            value = visit(node.value)
            if node.op != '=':
                name = builtins.BINOP_DUNDER_MAP[node.op[:-1]]
                signature = ty.FunctionType([ty.PosOrKwArg(None, target.type), ty.PosOrKwArg(None, value.type)], [], None, target.type)
                value = hir.FunctionCall(node.loc, target.type, hir.ExpressedIdentifier(node.loc, signature, name), [target, value], {})
            if isinstance(target, hir.DictLookup):
                return hir.DictStore(node.loc, node.type, target.keys, target.values, target.key, value)
            if isinstance(target, hir.Index):
                return hir.IndexAssign(node.loc, node.type, target, value)
            if isinstance(target, hir.MemberAccess):
                return hir.MemberAssign(node.loc, node.type, target, value)
            return replace(node, target=target, value=value, op='=')
        return replace(node, **{field.name: mapped(getattr(node, field.name)) for field in fields(node)})
    result = visit(root)
    for binding in registry.by_id.values():
        binding.type = map_type(binding.type)
        binding.store_type = map_type(binding.store_type)
    for node in hir.walk(result):
        if isinstance(node, hir.Declare) and node.binding_id in registry.by_id:
            binding = registry.by_id[node.binding_id]
            binding.declaration = node
            if isinstance(node.expr, hir.FunctionLiteral):
                binding.function = node.expr
    return result
