"""Storage proofs shared by public effects and runtime lowering.

Fixed scalar arrays and records of nested scalar fields can lend nonescaping field/element
addresses. Whole-owner loans also require proven stable storage: arrays may
only be read; scalar records may change fields. Proven read-only value arguments
can also lend stable local owners, without an explicit place. One bounded frame slot
suffices for each declaration, including loop iterations. These proofs
justify actual placement, not a hope that COW postpones allocation.
"""
from . import hir, ty

# An implementation budget, not a language limit. Larger storage retains the
# ordinary allocation path; a no-allocation contract needs another proof.
FRAME_STORAGE_BYTES = 4096


def scalar_record_size(type_):
    """A bounded upper size for inline records containing only scalar words.

    Count repeated field types each time; cycles or oversized shapes exhaust
    the same budget and cannot authorize frame placement.
    """
    pending, size = [type_], 0
    while pending:
        shape = ty.structural_base(pending.pop())
        if isinstance(shape, ty.ObjectType):
            if any(method.lifecycle is not None for method in shape.methods):
                return None
            size += 8  # nominal tag/alignment upper bound
            pending.extend(field.type for field in shape.fields)
        elif shape == 'bool' or ty.fixed_integer_layout(shape) is not None:
            size += 8
        else:
            return None
        if size > FRAME_STORAGE_BYTES:
            return None
    return size


def literal_storage(value):
    """Literal nodes initialized within one proven fixed record's storage."""
    result, pending = set(), [value]
    while pending:
        node = pending.pop()
        result.add(id(node))
        if isinstance(node, hir.CopyValue) and isinstance(node.value, (hir.ObjectLiteral, hir.CopyValue)):
            if ty.structural_base(node.value.type) == ty.structural_base(node.type):
                pending.append(node.value)
        if isinstance(node, hir.ObjectLiteral):
            shape = ty.structural_base(node.type)
            for field in node.fields:
                expected = shape.field(field.name)
                if (isinstance(field.value, (hir.ObjectLiteral, hir.CopyValue)) and expected is not None
                        and ty.structural_base(field.value.type) == ty.structural_base(expected.type)):
                    pending.append(field.value)
    return result


def local_values(literal: hir.FunctionLiteral, nonescaping_places: set[int] | frozenset[int] = frozenset(), fixed_places: set[int] | frozenset[int] = frozenset(), borrowed_values: dict[int, set[int]] | None = None) -> dict[int, hir.Declare]:
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
        elif isinstance(value, (hir.ObjectLiteral, hir.CopyValue)):
            size = scalar_record_size(value.type)
        if size is not None and size <= FRAME_STORAGE_BYTES:
            candidates[node.binding_id] = (node, size)
    allowed, occurrences = {}, {}
    blocked = set(captured)
    whole_places = set()
    for node in nodes:
        if isinstance(node, hir.FunctionCall) and borrowed_values is not None:
            borrowed = borrowed_values.get(id(node), ())
            for arg in [*node.pos_args, *node.kw_args.values()]:
                if id(arg) in borrowed and isinstance(arg, hir.ExpressedIdentifier):
                    allowed[id(arg)] = allowed.get(id(arg), 0) + 1
        if isinstance(node, hir.CopyValue) and isinstance(node.value, hir.ExpressedIdentifier):
            allowed[id(node.value)] = allowed.get(id(node.value), 0) + 1
        if isinstance(node, (hir.Index, hir.ArrayLength)) and isinstance(node.array, hir.ExpressedIdentifier):
            allowed[id(node.array)] = allowed.get(id(node.array), 0) + 1
        if isinstance(node, hir.MemberAccess) and isinstance(node.value, hir.ExpressedIdentifier):
            allowed[id(node.value)] = allowed.get(id(node.value), 0) + 1
        if isinstance(node, hir.Place) and id(node) in fixed_places and isinstance(node.target, hir.ExpressedIdentifier):
            allowed[id(node.target)] = allowed.get(id(node.target), 0) + 1
            whole_places.add(node.target.binding_id)
        if isinstance(node, hir.Place) and id(node) not in nonescaping_places:
            # Only a solved call boundary can lend a field/element address.
            # Whole owners additionally need the storage guarantee above.
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
        # Whole-array places also need one frame slot for the descriptor handle.
        if binding in whole_places and isinstance(declaration.expr, hir.ArrayLiteral):
            size += 8
        if used + size <= FRAME_STORAGE_BYTES:
            result[binding] = declaration
            used += size
    return result


def local_arrays(literal: hir.FunctionLiteral, nonescaping_places: set[int] | frozenset[int] = frozenset(), fixed_places: set[int] | frozenset[int] = frozenset(), borrowed_values: dict[int, set[int]] | None = None) -> dict[int, hir.Declare]:
    return {binding: declaration for binding, declaration in local_values(literal, nonescaping_places, fixed_places, borrowed_values).items()
            if isinstance(declaration.expr, hir.ArrayLiteral)}
