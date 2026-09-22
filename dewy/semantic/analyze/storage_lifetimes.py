"""Keep container storage stable while built-in operations invoke callbacks.

A sort holds element addresses through option evaluation and key invocation.
Value parameters/private local owners cannot be reached by an unrelated key;
captured, exposed and borrowed owners need a call-graph or effect-row proof.
"""
from collections import ChainMap

from .. import bindings, effect_rows as rows, hir, ty
from ..errors import user_error
from ...reporting import Pointer
from . import effects, predicate_effects


def validate(root, registry, srcfile):
    candidates = []
    private_by_function = {}
    borrowed_parameters = set()
    captured = set()
    exposed = set()
    written = set()
    aliases = {}

    def owner(binding):
        seen = set()
        while binding is not None and binding not in seen:
            seen.add(binding)
            entry = registry.by_id.get(binding)
            declaration = entry.declaration if entry is not None else None
            if not isinstance(declaration, hir.Declare) or not declaration.view:
                break
            binding = bindings.access_path(declaration.expr, unwrap=bindings._unwrap_fact_route, dictionaries=True).binding_id
        return binding

    def root_of(value):
        return owner(bindings.access_path(value, unwrap=bindings._unwrap_fact_route, dictionaries=True).binding_id)

    seen_nodes = set()
    pending_nodes = [(root, srcfile, None)]

    def scan(node, source, function=None):
        if id(node) in seen_nodes:
            return
        seen_nodes.add(id(node))
        if isinstance(node, hir.FunctionLiteral):
            source = node.source or source
            function = id(node)
            params = effects._literal_params(node)
            borrowed_parameters.update(p.binding_id for p in params if p.place)
            private = {p.binding_id for p in params if not p.place}
            local = {p.binding_id for p in params}
            reads = set()
            pending = list(hir.children(node))
            seen_body = set()
            while pending:
                part = pending.pop()
                if id(part) in seen_body:
                    continue
                seen_body.add(id(part))
                if isinstance(part, hir.FunctionLiteral):
                    continue
                if isinstance(part, hir.Declare):
                    local.add(part.binding_id)
                    if not part.view:
                        private.add(part.binding_id)
                if isinstance(part, hir.IteratorExpression):
                    local.add(part.target.binding_id)
                if isinstance(part, hir.ExpressedIdentifier):
                    reads.add(part.binding_id)
                pending.extend(hir.children(part))
            private_by_function[function] = private
            captured.update(owner(binding) for binding in reads - local)
        target = predicate_effects.write_target(node)
        if target is not None:
            written.add(root_of(target))
        if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
            aliases[node.binding_id] = owner(node.binding_id)
        if isinstance(node, hir.Place):
            exposed.add(root_of(node.target))
        if isinstance(node, hir.Transmute):
            exposed.add(root_of(node.expr))
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod) and node.func.name == 'sort':
            candidates.append((node, source, function, root_of(node.func.array)))
        if isinstance(node, hir.Program):
            for child, child_source in zip(node.items, node.item_sources):
                pending_nodes.append((child, child_source, function))
        else:
            for child in hir.children(node):
                pending_nodes.append((child, source, function))

    while pending_nodes:
        scan(*pending_nodes.pop())
    if not candidates:
        return
    # A callback may reach a global through a wrapper. Include captures when
    # a borrowed receiver might alias them; private callback locals don't
    # become ambient writes merely because they occur inside its body.
    tracked = (captured & written) | {binding for _, _, _, binding in candidates}
    tracked.discard(None)
    tracked.update(alias for alias, target in aliases.items() if target in tracked)
    writes = effects.analyze_global_writes(root, tracked)
    readonly = effects.read_only_places(root)
    no_mutation = rows.Contract(excluded=(rows.Atom('mutates'),))

    def nonmutating(value):
        signature = ty.unfold(ty.strip_refinement(value.type))
        return isinstance(signature, ty.FunctionType) and rows.implies(signature.effects, no_mutation)

    for call, source, function, binding in candidates:
        private = private_by_function.get(function, set())
        isolated = binding in private and binding not in captured and binding not in exposed
        # A borrowed place may denote any externally reachable owner. An
        # owned global/captured root has its own identity; a private owner
        # cannot be reached by the callback at all unless previously exposed.
        borrowed = binding in borrowed_parameters
        relevant = tracked if borrowed else {binding}
        key = call.kw_args.get('key')
        if key is not None and not isolated and not nonmutating(key):
            changed = {owner(item) for item in writes.get(id(call), tracked)}
            if changed & relevant:
                user_error(source, 'sort key may change its receiver',
                           Pointer(span=key.loc, message='the array storage must stay stable throughout key evaluation'),
                           hint='keep receiver mutations outside the sort, or provide a callback contract proving no mutation')
        # Options run after the receiver is selected. A selector expression
        # must not change that selection while lowering still holds it.
        for argument in [*call.pos_args, *call.kw_args.values()]:
            argument_writes = ChainMap({}, writes)
            for node in hir.walk(argument):
                if isinstance(node, hir.FunctionCall) and nonmutating(node.func):
                    argument_writes[id(node)] = set()
            changed = predicate_effects.mutated_bindings(argument, call_writes=argument_writes, read_only_places=readonly)
            if {owner(item) for item in changed} & relevant:
                user_error(source, 'sort option may change its receiver',
                           Pointer(span=argument.loc, message='this option changes the array while the sort is being prepared'),
                           hint='evaluate the option before selecting the array to sort')
