"""Storage proofs shared by public effects and runtime lowering.

A fixed scalar array used only for its length and element reads/writes has
no escaping descriptor or element address. One bounded frame slot suffices
for every execution of its declaration, including loop iterations. These
proofs describe actual placement, not a hope that COW postpones allocation.
"""
from . import hir, ty

# An implementation budget, not a language limit. Larger storage retains the
# ordinary allocation path; a no-allocation contract needs another proof.
FRAME_ARRAY_BYTES = 4096


def local_arrays(literal: hir.FunctionLiteral) -> dict[int, hir.Declare]:
    nodes = []
    captured = set()
    pending = [literal.body]
    while pending:
        node = pending.pop()
        if isinstance(node, hir.FunctionLiteral):
            captured.update(read.binding_id for read in hir.walk(node)
                            if isinstance(read, hir.ExpressedIdentifier))
            continue
        nodes.append(node)
        pending.extend(reversed(tuple(hir.children(node))))
    candidates = {}
    for node in nodes:
        if not isinstance(node, hir.Declare) or node.binding_id is None or node.view:
            continue
        value = node.expr
        if not isinstance(value, hir.ArrayLiteral) or not isinstance(value.type, ty.ArrayType):
            continue
        element = ty.strip_refinement(value.type.element)
        if element != 'bool' and ty.fixed_integer_layout(element) is None:
            continue
        if value.type.length != len(value.items) or any(isinstance(item, hir.Spread) for item in value.items):
            continue
        if 48 + 8 * len(value.items) <= FRAME_ARRAY_BYTES:
            candidates[node.binding_id] = node
    allowed, occurrences = {}, {}
    blocked = set(captured)
    for node in nodes:
        if isinstance(node, (hir.Index, hir.ArrayLength)) and isinstance(node.array, hir.ExpressedIdentifier):
            allowed[id(node.array)] = allowed.get(id(node.array), 0) + 1
        if isinstance(node, hir.Place):
            # Until the callee's escape proof is shared with this pass, even
            # a scalar element address conservatively excludes placement.
            blocked.update(read.binding_id for read in hir.walk(node.target)
                           if isinstance(read, hir.ExpressedIdentifier))
    for node in nodes:
        if isinstance(node, hir.ExpressedIdentifier):
            occurrences[id(node)] = occurrences.get(id(node), 0) + 1
    for node in nodes:
        if isinstance(node, hir.ExpressedIdentifier) and occurrences[id(node)] != allowed.get(id(node), 0):
            blocked.add(node.binding_id)
    result = {}
    used = 0
    for binding, declaration in candidates.items():
        if binding in blocked:
            continue
        size = 48 + 8 * len(declaration.expr.items)
        if used + size <= FRAME_ARRAY_BYTES:
            result[binding] = declaration
            used += size
    return result
