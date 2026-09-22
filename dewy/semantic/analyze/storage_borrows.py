"""Storage evidence shared by allocation contracts and argument lowering.

A read-only aggregate parameter, a stable fresh local owner, or one of their
projections can be forwarded without a snapshot when the caller and callee
operate on their own bindings through known calls. The whole-caller proof
excludes writes through later arguments too. Nonlocal
storage, raw operations, representation casts and unresolved callbacks keep
this proof unknown; ordinary lowering may have more precise borrow proofs.
"""
from collections import deque

from .. import hir, ty, bindings
from .effects import INDEX_STEP, _EffectAnalyzer, _literal_params, _unwrap
from . import predicate_effects

OPERATORS = frozenset({
    '__add__', '__sub__', '__mul__', '__div__', '__floordiv__', '__mod__',
    '__unary_sub__', '__not__', '__eq__', '__ne__', '__lt__', '__le__',
    '__gt__', '__ge__', '__and__', '__or__', '__xor__', '__nand__', '__nor__',
    '__xnor__', '__lshift__', '__rshift__',
})


def borrowable(type_):
    """Ordinary aggregate storage, without observable lifecycle operations."""
    shape = ty.structural_base(type_)
    if not isinstance(shape, (ty.ArrayType, ty.ObjectType, ty.StringType, ty.StringLiteralType)) and not ty.string_valued(shape):
        return False
    pending, seen = [shape], set()
    while pending:
        item = ty.structural_base(pending.pop())
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, ty.ObjectType):
            if any(method.lifecycle is not None for method in item.methods):
                return False
            pending.extend(field.type for field in item.fields)
        elif isinstance(item, ty.ArrayType):
            pending.append(item.element)
        elif isinstance(item, ty.TypeOr):
            pending.extend(item.items)
    return True


def forwarded_values(analysis: _EffectAnalyzer, summaries) -> dict[int, set[int]]:
    bodies, edges, blocked = {}, {}, set()
    stable_locals = {}
    eligible = {}

    def ordinary(type_):
        key = id(type_)
        if key not in eligible:
            eligible[key] = borrowable(type_)
        return eligible[key]

    for literal in analysis.literals:
        key = id(literal)
        local = {p.binding_id for p in _literal_params(literal)}
        body, pending, seen = [], [literal.body, *(p.value for p in _literal_params(literal)
                                                  if isinstance(p, hir.BoundParam))], set()
        while pending:
            node = pending.pop()
            if id(node) in seen or isinstance(node, hir.FunctionLiteral):
                continue
            seen.add(id(node))
            body.append(node)
            if isinstance(node, hir.Declare):
                local.add(node.binding_id)
            if isinstance(node, hir.IteratorExpression):
                local.add(node.target.binding_id)
            pending.extend(hir.children(node))
        local.discard(None)
        bodies[key] = body
        # Initial local-owner proof: no direct writes or exposed places during
        # the function. The call graph below excludes nonlocal/raw mutation.
        # Keep this conservative until statement-interval proofs are shared.
        written = set()
        for node in body:
            target = node.target if isinstance(node, hir.IteratorExpression) else predicate_effects.write_target(node)
            if target is not None:
                written.add(bindings.access_path(target, unwrap=bindings._unwrap_fact_route).binding_id)
        stable_locals[key] = {node.binding_id: node.expr.type for node in body
                             if isinstance(node, hir.Declare) and node.binding_id is not None and not node.view
                             and node.binding_id not in written
                             and isinstance(node.expr, (hir.ObjectLiteral, hir.ArrayLiteral))}
        for node in body:
            if isinstance(node, hir.RepresentationCast):
                blocked.add(key)
            elif isinstance(node, hir.ExpressedIdentifier):
                if (node.binding_id not in local
                        and not (node.binding_id is None and node.name in OPERATORS)
                        and analysis._flatten_callable(node, frozenset()) is None):
                    blocked.add(key)
            elif isinstance(node, hir.FunctionCall):
                targets = analysis._direct_targets(node)
                if targets is None:
                    func = _unwrap(node.func)
                    if not (isinstance(func, hir.ExpressedIdentifier)
                            and func.binding_id is None and func.name in OPERATORS):
                        blocked.add(key)
                else:
                    for target in targets:
                        edges.setdefault(id(target), set()).add(key)
    pending = deque(blocked)
    while pending:
        for caller in edges.get(pending.popleft(), ()):
            if caller not in blocked:
                blocked.add(caller)
                pending.append(caller)
    result = {}
    for literal in analysis.literals:
        if id(literal) in blocked:
            continue
        parameters = {p.binding_id: p for p in _literal_params(literal) if not p.place}
        for node in bodies[id(literal)]:
            if not isinstance(node, hir.FunctionCall):
                continue
            targets = analysis._direct_targets(node)
            if not targets:
                continue
            allowed = None
            for target in targets:
                pairs = analysis._pair_arguments(node, target)
                current, rejected = set(), set()
                for argument, parameter in pairs or ():
                    path = bindings.access_path(argument, unwrap=_unwrap)
                    source = path.root
                    own = parameters.get(source.binding_id) if isinstance(source, hir.ExpressedIdentifier) else None
                    incoming = summaries.for_param_binding(own.binding_id) if own else None
                    local = stable_locals[id(literal)].get(source.binding_id) if isinstance(source, hir.ExpressedIdentifier) else None
                    outgoing = summaries.for_param_binding(parameter.binding_id) if parameter else None
                    # No conversion or lifecycle operation at this boundary.
                    stable = (local is not None and ordinary(local)) or (
                        own is not None and ordinary(own.type) and incoming is not None
                        and (incoming.read_only or incoming.read_only_at(tuple(
                            INDEX_STEP if isinstance(step, hir.Index) else step.name for step in path.steps))))
                    expected = parameter.type if parameter is not None else None
                    same_storage = argument.type == expected or (
                        isinstance(argument.type, ty.ArrayType) and isinstance(expected, ty.ArrayType)
                        and argument.type.element == expected.element and expected.length is None)
                    if (stable and parameter is not None and ordinary(argument.type)
                            and same_storage and not parameter.place
                            and outgoing is not None and outgoing.read_only):
                        current.add(id(argument))
                    else:
                        rejected.add(id(argument))
                current -= rejected
                allowed = current if allowed is None else allowed & current
            if allowed:
                result[id(node)] = allowed
    return result
