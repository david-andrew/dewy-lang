"""Storage evidence shared by allocation contracts and argument lowering.

A read-only value parameter can be forwarded without a snapshot when the
caller and callee operate on their own bindings through known calls. The
whole-caller summary excludes writes through later arguments too. Nonlocal
storage, raw operations, representation casts and unresolved callbacks keep
this proof unknown; ordinary lowering may have more precise borrow proofs.
"""
from collections import deque

from .. import hir, ty
from .effects import _EffectAnalyzer, _literal_params, _unwrap

OPERATORS = frozenset({
    '__add__', '__sub__', '__mul__', '__div__', '__floordiv__', '__mod__',
    '__unary_sub__', '__not__', '__eq__', '__ne__', '__lt__', '__le__',
    '__gt__', '__ge__', '__and__', '__or__', '__xor__', '__nand__', '__nor__',
    '__xnor__', '__lshift__', '__rshift__',
})


def forwarded_arrays(analysis: _EffectAnalyzer, summaries) -> dict[int, set[int]]:
    bodies, edges, blocked = {}, {}, set()
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
                    source = _unwrap(argument)
                    own = parameters.get(source.binding_id) if isinstance(source, hir.ExpressedIdentifier) else None
                    incoming = summaries.for_param_binding(own.binding_id) if own else None
                    outgoing = summaries.for_param_binding(parameter.binding_id) if parameter else None
                    # No conversion or lifecycle operation at this boundary.
                    if (own is not None and parameter is not None and isinstance(argument.type, ty.ArrayType)
                            and argument.type == own.type == parameter.type
                            and not parameter.place and incoming is not None and incoming.read_only
                            and outgoing is not None and outgoing.read_only):
                        current.add(id(argument))
                    else:
                        rejected.add(id(argument))
                current -= rejected
                allowed = current if allowed is None else allowed & current
            if allowed:
                result[id(node)] = allowed
    return result
