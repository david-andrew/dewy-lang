"""Storage evidence shared by allocation contracts and argument lowering.

A read-only aggregate parameter, a stable fresh local owner, or one of their
projections can be forwarded without a snapshot when the caller and callee
operate on their own bindings through known calls. The whole-caller proof
excludes writes through later arguments too. Nonlocal
storage, raw operations, casts of existing storage and unresolved callbacks keep
this proof unknown; ordinary lowering may have more precise borrow proofs.
"""
from collections import deque
from dataclasses import dataclass, field

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
    if not isinstance(shape, (ty.ArrayType, ty.ObjectType, ty.TypeOr, ty.StringType, ty.StringLiteralType)) and not ty.string_valued(shape):
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


def independent_materialization(node):
    """Literal construction cannot expose a caller's existing storage.

    Keep casts of names/calls conservative, including byte views of strings.
    A closed literal/default has no such source, regardless of how many
    representation wrappers contextual typing inserts around it.
    """
    return all(isinstance(item, (hir.NoneValue, hir.Void, hir.Bool, hir.Integer,
        hir.String, hir.ArrayLiteral, hir.ObjectLiteral, hir.ValueCast,
        hir.RepresentationCast, hir.Obligation)) for item in hir.walk(node))


def private_origin(node):
    """Fresh value boundaries stay private through lazy conditional selection."""
    pending = [node]
    while pending:
        item = pending.pop()
        if isinstance(item, (hir.ObjectLiteral, hir.ArrayLiteral, hir.FunctionCall, hir.NoneValue)):
            continue
        if isinstance(item, hir.Flow):
            if item.default is None or any(not isinstance(arm, hir.IfArm) for arm in item.arms):
                return False
            pending.extend([item.default, *(arm.body for arm in item.arms)])
        elif isinstance(item, hir.Block) and len(item.items) == 1:
            pending.append(item.items[0])
        elif isinstance(item, hir.ValueCast):
            pending.append(item.expr)
        else:
            return False
    return True


def union_loan_source(node, expected_type=None):
    """A pure member injection/widening whose existing payload layout is kept.

    This only classifies the conversion. A call's storage proof must still
    establish stability and the callee's read-only use before lending it.
    Program-wide member tags permit exact-member widening of existing cells;
    family conversions and enum/string representation changes stay excluded.
    """
    source = node
    if isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
        expected_type = node.type if expected_type is None else expected_type
        source = node.expr
    elif expected_type is None:
        return None
    return source if ty.preserves_union_payload(source.type, expected_type) else None


def common_array_field(node):
    """A nonexceptional union field with one existing descriptor layout.

    Different alternatives may store the field at different offsets; dispatch
    still evaluates the receiver once. Retagging, exception forwarding and
    nested computed receivers keep their ordinary value boundary.
    """
    if (not isinstance(node, hir.ForwardingAccess) or node.exception_type != ty.BOTTOM_TYPE
            or not isinstance(shape := ty.structural_base(node.type), ty.ArrayType)
            or shape.length is not None
            or not isinstance(bindings.access_path(node.value, unwrap=_unwrap).root, hir.ExpressedIdentifier)):
        return False
    members = ty.runtime_union_members(node.value.type)
    if not members:
        return False
    for member in members:
        record = ty.structural_base(member)
        if not isinstance(record, ty.ObjectType):
            return False
        field = record.field(node.field)
        if field is None or ty.structural_base(field.type) != shape:
            return False
    return True


@dataclass(frozen=True)
class Proofs:
    arguments: dict[int, set[int]]
    local_views: set[int]
    literal_arguments: dict[int, set[int]]
    flow_views: set[int] = field(default_factory=set)
    flow_literals: set[int] = field(default_factory=set)
    flow_sources: set[int] = field(default_factory=set)


def array_selection(node):
    """Leaves of an array selection, without branch-local storage lifetimes.

    A small scalar literal can live in this function's frame; other leaves
    must name existing arrays. The caller proves their stability. Blocks with
    statements, loops, factories and conversions of elements stay owning.
    """
    shape = ty.structural_base(node.type)
    if not isinstance(node, hir.Flow) or not isinstance(shape, ty.ArrayType):
        return None
    leaves, pending = [], [node]
    while pending:
        item = pending.pop()
        # A nested join may retain a union of array lengths until its outer
        # context widens it. Wrappers do not own storage: check each leaf's
        # element representation instead of requiring a normalized join type.
        if isinstance(item, hir.Flow):
            if item.default is None or any(not isinstance(arm, hir.IfArm) for arm in item.arms):
                return None
            pending.extend([item.default, *(arm.body for arm in item.arms)])
        elif isinstance(item, hir.Block) and len(item.items) == 1:
            pending.append(item.items[0])
        elif isinstance(item, (hir.ValueCast, hir.RepresentationCast)):
            pending.append(item.expr)
        else:
            actual = ty.structural_base(item.type)
            if not isinstance(actual, ty.ArrayType) or actual.element != shape.element:
                return None
            if not isinstance(item, (hir.ArrayLiteral, hir.ExpressedIdentifier, hir.MemberAccess, hir.Index)) and not common_array_field(item):
                return None
            if isinstance(item, hir.ArrayLiteral) and (actual.length != len(item.items) or len(item.items) > 64 or any(isinstance(value, hir.Spread) for value in item.items)
                    or item.items and actual.element != 'bool' and ty.fixed_integer_layout(actual.element) is None):
                return None
            leaves.append(item)
    return leaves


def owning_array_reads(body, analysis, summaries, selection_reads=()):
    """An owning use should keep a join's ordinary last-use move protocol."""
    owning = set()
    for parent in body:
        borrowed = set()
        if isinstance(parent, hir.FunctionCall):
            targets = analysis._direct_targets(parent)
            allowed = None
            for target in targets or ():
                current = {id(value) for value, param in analysis._pair_arguments(parent, target) or ()
                           if param is not None and not param.place
                           and (summary := summaries.for_param_binding(param.binding_id)) is not None
                           and summary.read_only}
                allowed = current if allowed is None else allowed & current
            borrowed = allowed or set()
        for child in hir.children(parent):
            if not isinstance(child, hir.ExpressedIdentifier) or child.binding_id is None:
                continue
            observed = (id(child) in selection_reads or
                isinstance(parent, (hir.Index, hir.ArrayLength)) and child is parent.array
                or isinstance(parent, hir.MemberAccess) and child is parent.value
                or isinstance(parent, hir.IteratorExpression) and child is parent.iterable
                or isinstance(parent, hir.ArrayMethod) and parent.name == 'join' and child is parent.array
                or id(child) in borrowed)
            if not observed:
                owning.add(child.binding_id)
    return owning


def record_loan_size(type_, memo):
    """Bounded inline bytes, including possible descendant record layouts.

    Array descriptors are borrowed handles, never inline element storage.
    Sum the family alternatives conservatively rather than depending on the
    backend's padding choices. Repeated fields count repeatedly; cycles and
    oversized families exhaust the same finite frame budget.
    """
    key = id(type_)
    if key in memo:
        return memo[key]
    pending, size = [(type_, True)], 0
    while pending:
        selected, family = pending.pop()
        shape = ty.structural_base(selected)
        if isinstance(shape, ty.ObjectType):
            if any(method.lifecycle is not None for method in shape.methods):
                size = None
                break
            pending.extend((field.type, True) for field in shape.fields)
            if family:
                pending.extend((ty.USER_BRAND_TYPES[name], False)
                               for name in ty.brand_alternatives(shape))
        elif scalar_loan_cell(shape):
            size += 8  # scalar union: tag plus one scalar payload word
        elif not (isinstance(shape, ty.ArrayType) and shape.length is None
                  or shape == 'bool' or ty.fixed_integer_layout(shape) is not None):
            size = None
            break
        size += 8  # word, array handle, or record tag/alignment allowance
        if size > 4096:
            size = None
            break
    memo[key] = size
    return size


def scalar_loan_cell(type_):
    """A two-word tag cell with no descriptor, owner or cleanup inside it."""
    shape = ty.structural_base(type_)
    return isinstance(shape, ty.TypeOr) and bool(shape.items) and all(
        (plain := ty.structural_base(member)) in ('none', 'bool', 'true', 'false')
        or ty.fixed_integer_layout(plain) is not None for member in shape.items)


def record_loan_fields(node, sizes):
    """A call-scoped root lends stable fields without acquiring owners.

    Inline records containing words and array handles use the same lifetime
    proof as array fields. Scalar tag cells own no payload; other cells and
    fixed arrays retain their ordinary path.
    """
    if not isinstance(node, hir.ObjectLiteral) or not borrowable(node.type):
        return None
    if record_loan_size(node.type, sizes) is None:
        return None
    shape = ty.structural_base(node.type)
    if not isinstance(shape, ty.ObjectType) or len(shape.fields) != len(node.fields):
        return None
    borrowed = []
    for field in node.fields:
        expected = shape.field(field.name)
        if expected is None:
            return None
        stored = ty.structural_base(expected.type)
        actual = ty.structural_base(field.value.type)
        if isinstance(stored, ty.ArrayType) and stored.length is None:
            if actual != stored:
                return None
            borrowed.append(field.value)
        elif isinstance(stored, ty.ObjectType) and actual == stored:
            borrowed.append(field.value)
        elif scalar_loan_cell(stored) and (
                actual == stored or actual in ('none', 'bool', 'true', 'false')
                or ty.fixed_integer_layout(actual) is not None
                or isinstance(actual, ty.IntegerLiteralType)):
            pass
        elif stored == 'bool' and actual in ('bool', 'true', 'false'):
            pass
        elif ty.fixed_integer_layout(stored) is not None and (actual == stored or
                isinstance(actual, ty.IntegerLiteralType) and ty.integer_literal_fits(actual.value, stored)):
            pass
        else:
            return None
    return borrowed


def prove(analysis: _EffectAnalyzer, summaries) -> Proofs:
    bodies, edges, blocked = {}, {}, set()
    stable_locals = {}
    writes, captured = {}, set()
    eligible = {}
    loan_sizes = {}

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
            if isinstance(node, hir.ObjectLiteral):
                # Later fields/defaults can name earlier fields. These names
                # belong to this construction, not to an ambient owner.
                local.update(field.binding_id for field in node.fields)
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
        # Private fresh owners cannot alias ambient state. Keep only owners
        # whose storage never crosses an unmodelled/raw boundary in this body;
        # ordinary resolved value calls manage their own independent argument.
        for node in body:
            exposed = []
            if isinstance(node, (hir.Transmute, hir.RepresentationCast)):
                if union_loan_source(node) is None:
                    exposed.append(node.expr)
            elif isinstance(node, hir.FunctionCall) and analysis._direct_targets(node) is None:
                func = _unwrap(node.func)
                modeled = (isinstance(func, hir.ExpressedIdentifier) and func.binding_id is None and func.name in OPERATORS
                           or isinstance(func, hir.ArrayMethod) and not (func.name == 'sort' and 'key' in node.kw_args))
                if not modeled:
                    exposed.extend([*node.pos_args, *node.kw_args.values()])
                    if isinstance(func, hir.ArrayMethod):
                        exposed.append(func.array)
            for value in exposed:
                path = bindings.access_path(value, unwrap=bindings._unwrap_fact_route)
                if isinstance(path.root, hir.ExpressedIdentifier):
                    written.add(path.root.binding_id)
        writes[key] = written
        captured.update(node.binding_id for node in body if isinstance(node, hir.ExpressedIdentifier)
                        and node.binding_id is not None and node.binding_id not in local)
        stable_locals[key] = {node.binding_id: node.expr.type for node in body
                             if isinstance(node, hir.Declare) and node.binding_id is not None and not node.view
                             and node.binding_id not in written
                             # Ordinary calls return independent values. The
                             # graph check below still excludes unknown/raw
                             # effects and writes/captures of these locals.
                             and private_origin(node.expr)}
        for node in body:
            if (isinstance(node, hir.RepresentationCast) and not independent_materialization(node.expr)
                    and union_loan_source(node) is None):
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
    # Call roots may pass through known read-only helpers, provided every
    # path ends in projections. An owning use rejects its parameter and all
    # forwarders; forwarding cycles with no owning endpoint remain loans.
    # This is separate from effect purity: a read-only callee can still copy
    # its complete input into a local and require the owning-input protocol.
    unprojected_reads = set()
    forwarders = {}
    for literal in analysis.literals:
        for node in [literal, *bodies[id(literal)]]:
            forwarded = {}
            if isinstance(node, hir.FunctionCall):
                targets = analysis._direct_targets(node)
                common = None
                for target in targets or ():
                    current = {}
                    for value, param in analysis._pair_arguments(node, target) or ():
                        summary = summaries.for_param_binding(param.binding_id) if param is not None else None
                        if param is not None and not param.place and summary is not None and summary.read_only:
                            current.setdefault(id(value), set()).add(param.binding_id)
                    common = set(current) if common is None else common & current.keys()
                    for value, parameters in current.items():
                        forwarded.setdefault(value, set()).update(parameters)
                forwarded = {value: parameters for value, parameters in forwarded.items() if value in (common or ())}
            for child in hir.children(node):
                if not isinstance(child, hir.ExpressedIdentifier) or child.binding_id is None:
                    continue
                if isinstance(node, hir.MemberAccess) and child is node.value:
                    continue
                if id(child) in forwarded:
                    for parameter in forwarded[id(child)]:
                        forwarders.setdefault(parameter, set()).add(child.binding_id)
                else:
                    unprojected_reads.add(child.binding_id)
    pending = deque(unprojected_reads)
    while pending:
        for caller in forwarders.get(pending.popleft(), ()):
            if caller not in unprojected_reads:
                unprojected_reads.add(caller)
                pending.append(caller)
    # A nested function may capture an owner even if that function is not
    # called directly here. It cannot enter the private-owner proof.
    stable_locals = {key: {binding: type_ for binding, type_ in owners.items() if binding not in captured}
                     for key, owners in stable_locals.items()}
    result, local_views, literal_arguments = {}, set(), {}
    flow_views, flow_literals, flow_sources = set(), set(), set()
    for literal in analysis.literals:
        # Incoming storage may alias a global written by a nested call.
        # Private fresh owners have no such alias: their direct writes,
        # exposure and captures were excluded above. Keep the graph-wide
        # restriction for parameters, without applying it to private locals.
        params = _literal_params(literal)
        # One incoming place cannot alias another place formal. Its unwritten
        # projections may lend storage under the same route effect proof.
        # Multiple places may alias at the call, so keep those unknown until
        # their cross-parameter alias relationships are proved as well.
        single_place = sum(bool(p.place) for p in params) == 1
        parameters = {} if id(literal) in blocked else {
            p.binding_id: p for p in params if not p.place or single_place}
        # An unwritten projection can lend its parameter's existing storage.
        # No retagging, lifecycle operation, capture, or escaping address is
        # admitted by this shared proof. More precise scoped views remain a
        # lowerer optimization until their evidence is shared here too.
        pending_views = [node for node in bodies[id(literal)] if isinstance(node, hir.Declare)]
        waiting_views = {}
        while pending_views:
            node = pending_views.pop()
            if (not isinstance(node, hir.Declare) or node.binding_id is None
                    or node.binding_id in writes[id(literal)] or node.binding_id in captured
                    or not isinstance(node.expr, (hir.Index, hir.MemberAccess))
                    or not ordinary(node.expr.type)):
                continue
            path = bindings.access_path(node.expr, unwrap=_unwrap)
            source = path.root
            own = parameters.get(source.binding_id) if isinstance(source, hir.ExpressedIdentifier) else None
            incoming = summaries.for_param_binding(own.binding_id) if own else None
            if not isinstance(source, hir.ExpressedIdentifier) or source.binding_id is None:
                continue
            private = stable_locals[id(literal)].get(source.binding_id)
            if own is None and source.binding_id not in local_views and not (private is not None and ordinary(private)):
                # Each candidate depends on one named owner. Wake it only
                # when that owner is proved; cycles and unknown owners never
                # seed a proof. No repeated scan of the complete body.
                waiting_views.setdefault(source.binding_id, []).append(node)
                continue
            # A sibling write does not change this projection's storage.
            # Use the same route permission as direct argument forwarding;
            # whole-owner writes, escapes and overlapping routes still fail.
            if (own is not None and (not ordinary(own.type) or incoming is None
                    or not incoming.read_only_at(tuple(
                        INDEX_STEP if isinstance(step, hir.Index) else step.name for step in path.steps)))):
                continue
            value = node.expr
            shape = ty.structural_base(value.array.type if isinstance(value, hir.Index) else value.value.type)
            stored = shape.element if isinstance(value, hir.Index) and isinstance(shape, ty.ArrayType) else None
            if isinstance(value, hir.MemberAccess) and isinstance(shape, ty.ObjectType):
                field = shape.field(value.name)
                stored = field.type if field is not None else None
            if stored is None or ty.structural_base(stored) != ty.structural_base(value.type):
                continue
            if node.annotation is not None and ty.structural_base(node.annotation) != ty.structural_base(value.type):
                continue
            local_views.add(node.binding_id)
            pending_views.extend(waiting_views.pop(node.binding_id, ()))
        def stable_value(value, selections=()):
            path = bindings.access_path(value, unwrap=_unwrap, forwarding=common_array_field(value))
            source = path.root
            if not isinstance(source, hir.ExpressedIdentifier):
                return False
            own = parameters.get(source.binding_id)
            incoming = summaries.for_param_binding(own.binding_id) if own else None
            local = stable_locals[id(literal)].get(source.binding_id)
            stable = source.binding_id in local_views or source.binding_id in selections or (local is not None and ordinary(local)) or (
                own is not None and ordinary(own.type) and incoming is not None
                and incoming.read_only_at(tuple(INDEX_STEP if isinstance(step, hir.Index) else
                                                step.field if isinstance(step, hir.ForwardingAccess) else step.name
                                                for step in path.steps)))
            # A narrowed field/element may still live in a tagged cell or a
            # different layout. Do not reinterpret that storage as a handle.
            for step in path.steps:
                if common_array_field(step):
                    continue  # every alternative was checked against this descriptor layout
                parent = ty.structural_base(step.array.type if isinstance(step, hir.Index) else step.value.type)
                field = parent.field(step.name) if isinstance(step, hir.MemberAccess) and isinstance(parent, ty.ObjectType) else None
                stored = parent.element if isinstance(step, hir.Index) and isinstance(parent, ty.ArrayType) else field.type if field else None
                if stored is None or ty.structural_base(stored) != ty.structural_base(step.type):
                    return False
            return stable

        # A selected local need not own a snapshot when every existing arm
        # keeps its owner stable and every fresh arm fits bounded frame storage.
        # Mutating/escaping uses still pay their normal value-boundary cost.
        flow_bytes = 0
        candidates, selection_reads = {}, set()
        for node in bodies[id(literal)]:
            if (not isinstance(node, hir.Declare) or not isinstance(node.expr, hir.Flow)
                    or node.binding_id is None or node.view
                    or node.binding_id in writes[id(literal)] or node.binding_id in captured
                    or not ordinary(node.expr.type)):
                continue
            leaves = array_selection(node.expr)
            if leaves is None or (node.annotation is not None
                                  and ty.structural_base(node.annotation) != ty.structural_base(node.expr.type)):
                continue
            literals = [item for item in leaves if isinstance(item, hir.ArrayLiteral)]
            size = sum(64 + 8 * len(item.items) for item in literals)
            if flow_bytes + size > 4096:
                continue
            flow_bytes += size
            candidates[node.binding_id] = (leaves, literals)
            selection_reads.update(id(item) for item in leaves if isinstance(item, hir.ExpressedIdentifier))

        # A selected view may itself feed another selection. First prove all
        # sources from independent roots, then revoke the connected loans if
        # any reader needs an owner. Neither a cycle nor a failed reader can
        # bootstrap borrowing. Each edge is visited a bounded number of times.
        owning_reads = owning_array_reads(bodies[id(literal)], analysis, summaries, selection_reads) if candidates else set()
        dependencies, readers, invalid = {}, {}, set()
        for binding, (leaves, _) in candidates.items():
            needed = set()
            if binding in owning_reads:
                invalid.add(binding)
            for leaf in leaves:
                if isinstance(leaf, hir.ArrayLiteral):
                    continue
                if not stable_value(leaf, candidates):
                    invalid.add(binding)
                    continue
                source = bindings.access_path(leaf, unwrap=_unwrap, forwarding=common_array_field(leaf)).root
                if isinstance(source, hir.ExpressedIdentifier) and source.binding_id in candidates:
                    needed.add(source.binding_id)
                    readers.setdefault(source.binding_id, set()).add(binding)
            dependencies[binding] = needed
        counts = {binding: len(needed) for binding, needed in dependencies.items()}
        pending = [binding for binding, count in counts.items() if not count and binding not in invalid]
        proven = set()
        while pending:
            binding = pending.pop()
            proven.add(binding)
            for reader in readers.get(binding, ()):
                counts[reader] -= 1
                if not counts[reader] and reader not in invalid:
                    pending.append(reader)
        invalid.update(candidates.keys() - proven)
        pending = list(invalid)
        while pending:
            binding = pending.pop()
            for neighbor in dependencies.get(binding, set()) | readers.get(binding, set()):
                if neighbor not in invalid:
                    invalid.add(neighbor)
                    pending.append(neighbor)
        for binding, (leaves, literals) in candidates.items():
            if binding in invalid:
                continue
            flow_views.add(binding)
            local_views.add(binding)
            flow_literals.update(id(item) for item in literals)
            flow_sources.update(id(item) for item in leaves if isinstance(item, hir.ExpressedIdentifier))

        # Separate from ordinary local placement: at most 4 KiB of fixed
        # call roots per function, reused across loop iterations.
        literal_bytes = 0
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
                    expected = parameter.type if parameter is not None else None
                    loan = union_loan_source(argument, expected) if expected is not None else None
                    path = bindings.access_path(argument if loan is None else loan, unwrap=_unwrap,
                                                forwarding=common_array_field(argument))
                    source = path.root
                    own = parameters.get(source.binding_id) if isinstance(source, hir.ExpressedIdentifier) else None
                    incoming = summaries.for_param_binding(own.binding_id) if own else None
                    local = stable_locals[id(literal)].get(source.binding_id) if isinstance(source, hir.ExpressedIdentifier) else None
                    outgoing = summaries.for_param_binding(parameter.binding_id) if parameter else None
                    # An exact union wrapper may lend the same stable payload.
                    stable = (isinstance(source, hir.ExpressedIdentifier)
                              and source.binding_id in local_views) or (local is not None and ordinary(local)) or (
                        own is not None and ordinary(own.type) and incoming is not None
                        and (incoming.read_only or incoming.read_only_at(tuple(
                            INDEX_STEP if isinstance(step, hir.Index) else
                            step.field if isinstance(step, hir.ForwardingAccess) else step.name
                            for step in path.steps))))
                    same_storage = argument.type == expected or (
                        isinstance(argument.type, ty.ArrayType) and isinstance(expected, ty.ArrayType)
                        and argument.type.element == expected.element and expected.length is None)
                    same_storage |= loan is not None
                    fields = record_loan_fields(argument, loan_sizes)
                    if (fields is not None and argument.type == expected
                            and parameter is not None and parameter.binding_id not in unprojected_reads
                            and all(stable_value(field) for field in fields)):
                        stable = True
                    if (stable and parameter is not None and ordinary(argument.type)
                            and same_storage and not parameter.place
                            and outgoing is not None and outgoing.read_only):
                        current.add(id(argument))
                    else:
                        rejected.add(id(argument))
                current -= rejected
                allowed = current if allowed is None else allowed & current
            if allowed:
                loans = set()
                for argument in [*node.pos_args, *node.kw_args.values()]:
                    if id(argument) in allowed and isinstance(argument, hir.ObjectLiteral):
                        size = record_loan_size(argument.type, loan_sizes)
                        if size is not None and literal_bytes + size <= 4096:
                            literal_bytes += size
                            loans.add(id(argument))
                        else:
                            allowed.discard(id(argument))
                if loans:
                    literal_arguments[id(node)] = loans
                result[id(node)] = allowed
    return Proofs(result, local_views, literal_arguments, flow_views, flow_literals, flow_sources)
