"""Storage proofs shared by public effects and runtime lowering.

Fixed scalar arrays used only for length/element access, and scalar records
used only for field access, have no escaping address. One bounded frame slot
suffices for each declaration, including loop iterations. These proofs
justify actual placement, not a hope that COW postpones allocation.
"""
from . import hir, ty

# An implementation budget, not a language limit. Larger storage retains the
# ordinary allocation path; a no-allocation contract needs another proof.
FRAME_STORAGE_BYTES = 4096


def local_values(literal: hir.FunctionLiteral) -> dict[int, hir.Declare]:
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
        size = None
        if isinstance(value, hir.ArrayLiteral) and isinstance(value.type, ty.ArrayType):
            element = ty.strip_refinement(value.type.element)
            scalar = element == 'bool' or ty.fixed_integer_layout(element) is not None
            if scalar and value.type.length == len(value.items) and not any(isinstance(item, hir.Spread) for item in value.items):
                size = 48 + 8 * len(value.items)
        elif isinstance(value, hir.ObjectLiteral):
            shape = ty.structural_base(value.type)
            if (isinstance(shape, ty.ObjectType)
                    and not any(method.lifecycle is not None for method in shape.methods)
                    and all(ty.strip_refinement(field.type) == 'bool' or ty.fixed_integer_layout(field.type) is not None
                            for field in shape.fields)):
                # Include the optional nominal tag, with an upper bound for
                # every scalar field. Actual layout may pack narrower words.
                size = 8 + 8 * len(shape.fields)
        if size is not None and size <= FRAME_STORAGE_BYTES:
            candidates[node.binding_id] = (node, size)
    allowed, occurrences = {}, {}
    blocked = set(captured)
    for node in nodes:
        if isinstance(node, (hir.Index, hir.ArrayLength)) and isinstance(node.array, hir.ExpressedIdentifier):
            allowed[id(node.array)] = allowed.get(id(node.array), 0) + 1
        if isinstance(node, hir.MemberAccess) and isinstance(node.value, hir.ExpressedIdentifier):
            allowed[id(node.value)] = allowed.get(id(node.value), 0) + 1
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
    for binding, (declaration, size) in candidates.items():
        if binding in blocked:
            continue
        if used + size <= FRAME_STORAGE_BYTES:
            result[binding] = declaration
            used += size
    return result


def local_arrays(literal: hir.FunctionLiteral) -> dict[int, hir.Declare]:
    return {binding: declaration for binding, declaration in local_values(literal).items()
            if isinstance(declaration.expr, hir.ArrayLiteral)}
