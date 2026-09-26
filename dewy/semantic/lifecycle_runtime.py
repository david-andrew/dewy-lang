"""Materialize ownership operations before runtime lowering.

Fresh records and arrays own their nested resources; factories, ordinary
by-value parameters and results transfer fresh owners. Checked @ parameters
borrow. Same-scope bindings can move at last use, and custom copy/move hooks
remain checked calls. Drop precedes field/element storage cleanup.

Branch consumption uses last-use proofs and conditional cleanup. Replacing an
owner re-establishes its lifetime, including across checked loop backedges.
Last-use components transfer through synthesized wrappers; using the remaining
parts of a partially transferred owner still needs further lifetime analysis.
"""
from dataclasses import replace

from . import hir, ty, lifecycle, bindings, resource_iteration
from ..parser import t0
from .errors import not_implemented, user_error
from ..reporting import Pointer
from .analyze import public_effects, effects, predicate_effects
from .analyze.ownership_liveness import conditional_consumptions, field_route


def prepare(root: hir.Block, srcfile, *, selected: set[int] | None = None, validate: bool = True,
            effect_context: hir.AST | None = None):
    if isinstance(root, hir.Program) and root.ownership_prepared:
        return root
    declarations = {node.binding_id: node for node in root.items
                    if isinstance(node, hir.Declare) and isinstance(node.expr, hir.FunctionLiteral)
                    and node.expr.lifecycle is not None}
    if not declarations:
        return root

    current_source = srcfile
    def reject(node, detail):
        not_implemented(current_source, node.loc, 'lifecycle ownership lowering: ' + detail)

    resource_cache = {}
    def resource(type_):
        key = id(type_)
        if key in resource_cache:
            return resource_cache[key]
        pending, seen = [type_], set()
        while pending:
            type_ = ty.structural_base(pending.pop())
            if id(type_) in seen:
                continue
            seen.add(id(type_))
            if isinstance(type_, ty.ObjectType):
                if any(method.lifecycle is not None for method in type_.methods):
                    resource_cache[key] = type_
                    return type_
                pending.extend(field.type for field in type_.fields)
            elif isinstance(type_, ty.ArrayType):
                pending.append(type_.element)
            elif isinstance(type_, ty.TypeOr):
                pending.extend(type_.items)
        resource_cache[key] = None
        return None

    for declaration in declarations.values():
        literal = declaration.expr
        current_source = literal.source or srcfile
        receiver = ty.structural_base(literal.pos_or_kw_args[0].type)
        if literal.lifecycle not in ('drop', 'copy', 'move') or not isinstance(receiver, ty.ObjectType):
            reject(declaration, 'an invalid lifecycle receiver')

    current_source = srcfile

    def mentions_resource(literal):
        for node in hir.walk(literal):
            if isinstance(node, hir.FunctionLiteral):
                params = [*node.pos_or_kw_args, *node.kw_only_args]
                if node.rest_args is not None:
                    params.append(node.rest_args)
                if resource(node.rettype) is not None or any(resource(p.type) is not None for p in params):
                    return True
            if resource(node.type) is not None:
                return True
        return False

    registry = root.binding_registry if isinstance(root, hir.Program) else None
    if registry is None:
        reject(root, 'checked ownership binding metadata')

    iteration_loans = resource_iteration.prepare(root, registry, resource)

    # Splitting a resource mutation into cleanup and storage operations must
    # not reselect a receiver changed by an argument or selector. Use the
    # existing transitive may-write summaries, including captured roots.
    receivers = {bindings.access_path(node.func.array, dictionaries=True).binding_id
                 for node in hir.walk(root) if isinstance(node, hir.FunctionCall)
                 and isinstance(node.func, hir.ArrayMethod) and node.func.name == 'truncate'
                 and resource(node.func.array.type) is not None}
    receivers.update(bindings.access_path(node.target, dictionaries=True).binding_id
                     for node in hir.walk(root) if isinstance(node, (hir.MemberAssign, hir.IndexAssign))
                     and resource(node.target.type) is not None)
    for node in hir.walk(root):
        if (isinstance(node, (hir.DictStore, hir.DictRemove, hir.DictLookup))
                and node.values is not None and resource(node.values.type) is not None):
            receivers.add(bindings.access_path(node.keys, dictionaries=True).binding_id)
            if isinstance(node, hir.DictLookup):
                # A synthesized component copy can compact its dictionary
                # receiver. Membership survives, but cached physical slots do
                # not. Reprobe resource entries until that representation
                # effect can invalidate only the affected cached positions.
                node.position = node.static_position = None
    receivers.update(bindings.access_path(node.item, unwrap=bindings._unwrap_fact_route, dictionaries=True).binding_id
                     for node in hir.walk(root) if isinstance(node, hir.Return) and node.item is not None
                     and resource(node.item.type) is not None)
    receivers.update(bindings.access_path(node, dictionaries=True).binding_id for node in hir.walk(root)
                     if isinstance(node, (hir.MemberAccess, hir.Index)) and resource(node.type) is not None)
    receivers.discard(None)
    argument_writes = effects.analyze_global_writes(effect_context or root, receivers)
    readonly_arguments = effects.read_only_places(root, effect_context) if receivers else set()
    recursive_drops = {}
    array_drops = {}
    array_clears = {}
    array_suffixes = {}
    component_copies = {}
    generated = []
    ownership_flags = {}
    # Components consumed on some paths only: owner -> {field path: flag}.
    # The flag is true while the owner still holds that component.
    component_flags = {}
    extractions = {}  # last-use components; the remaining owner keeps its lexical cleanup

    def move_remainder(shape):
        """Fields left behind by a custom move, excluding inherited transfers.

        A generated inheritance wrapper adopts the added fields. Only the
        portion handled by the original user hook still needs field cleanup;
        walking through composed parents also handles deeper descendants.
        """
        current = shape
        while True:
            hook = next((method for method in current.methods if method.lifecycle == 'move'), None)
            operation = declarations.get(hook.binding_id) if hook is not None else None
            if operation is None or not operation.expr.lifecycle_composition:
                return current.fields
            parent = ty.USER_BRAND_PARENTS.get(current.brand)
            assert parent is not None
            current = ty.USER_BRAND_TYPES[parent]

    def cleanup(owners, loc, fields_only=frozenset(), *, suffix=None, selected=None, extracted=None):
        result = []
        def drop(value, type_, ancestors, run_hook=True, into=result, tail=None, extraction=None, additional=(), inline_array=False, guards=None):
            if guards and () in guards:
                # Drop a conditionally consumed component only while its
                # owner still holds it.
                calls = []
                drop(value, type_, ancestors, run_hook, into=calls, tail=tail, extraction=extraction,
                     additional=additional, inline_array=inline_array,
                     guards={path: flag for path, flag in guards.items() if path})
                if calls:
                    into.append(hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(loc, ty.VOID_TYPE, guards[()],
                                                                        hir.Block(loc, ty.VOID_TYPE, calls, True))], None))
                return
            routes = (() if extraction is None else (extraction,)) + tuple(additional)
            if extraction is not None and not extraction[0]:
                if not extraction[1]:
                    return  # This component now belongs to the returned value.
                run_hook = False  # A custom move leaves only component cleanup.
                extraction = None
                routes = ()
            if resource(type_) is None:
                return
            shape = ty.structural_base(type_)
            if id(shape) in ancestors and not routes and not guards:
                # A recursive value has finite runtime storage but an infinite
                # structural expansion. Close that expansion with a borrowed
                # helper call, publishing its identity before checking its body.
                key = (id(shape), run_hook)
                operation = recursive_drops.get(key)
                if operation is None:
                    name = f'__dewy_drop_recursive_{registry.next_id}'
                    binding = registry.allocate(object(), name, 'value', loc)
                    parameter = registry.allocate(object(), '__source', 'param', loc)
                    parameter.type = shape
                    signature = ty.FunctionType([ty.PosOrKwArg('__source', shape, place=True)], [], None, ty.VOID_TYPE)
                    binding.type = signature
                    operation = hir.ExpressedIdentifier(loc, signature, name, binding_id=binding.id)
                    recursive_drops[key] = operation
                    receiver = hir.ExpressedIdentifier(loc, shape, parameter.name, binding_id=parameter.id)
                    body = []
                    drop(receiver, shape, set(), run_hook, into=body)
                    literal = hir.FunctionLiteral(loc, signature,
                        [hir.Param(parameter.name, shape, binding_id=parameter.id, place=True)],
                        [], None, ty.VOID_TYPE, hir.Block(loc, ty.VOID_TYPE, body, True), source=current_source)
                    declared = hir.Declare(loc, ty.VOID_TYPE, 'const', name, signature, literal, binding_id=binding.id)
                    binding.function = literal
                    binding.declaration = declared
                    generated.append(declared)
                into.append(hir.FunctionCall(loc, ty.VOID_TYPE, replace(operation, loc=loc),
                                             [hir.Place(loc, shape, value)], {}))
                return
            if isinstance(shape, ty.ArrayType) and extraction is not None and not inline_array and not isinstance(value, hir.ExpressedIdentifier):
                # Give each array traversal a stable borrowed root. In a
                # nested selection the caller's outer cursor changes; its
                # indexed expression cannot serve as an invariant identity.
                name = f'__dewy_drop_selected_{registry.next_id}'
                binding = registry.allocate(object(), name, 'value', loc)
                parameter = registry.allocate(object(), '__items', 'param', loc)
                parameter.type = shape
                params = [hir.Param(parameter.name, shape, binding_id=parameter.id, place=True)]
                arguments = [hir.Place(loc, shape, value)]
                translated = []
                for route, moved in routes:
                    path = []
                    for selector in route:
                        if isinstance(selector, (str, hir.Integer)):
                            path.append(selector)
                            continue
                        param = registry.allocate(object(), f'__index_{len(params)}', 'param', loc)
                        param.type = 'int64'
                        params.append(hir.Param(param.name, 'int64', binding_id=param.id))
                        arguments.append(selector)
                        path.append(hir.ExpressedIdentifier(loc, 'int64', param.name, binding_id=param.id))
                    translated.append((tuple(path), moved))
                signature = ty.FunctionType([ty.PosOrKwArg(p.name, p.type, place=p.place) for p in params], [], None, ty.VOID_TYPE)
                binding.type = signature
                receiver = hir.ExpressedIdentifier(loc, shape, parameter.name, binding_id=parameter.id)
                body = []
                drop(receiver, shape, set(), into=body, extraction=translated[0], additional=translated[1:], inline_array=True)
                literal = hir.FunctionLiteral(loc, signature, params, [], None, ty.VOID_TYPE,
                    hir.Block(loc, ty.VOID_TYPE, body, True), source=current_source)
                declared = hir.Declare(loc, ty.VOID_TYPE, 'const', name, signature, literal, binding_id=binding.id)
                binding.function = literal
                binding.declaration = declared
                generated.append(declared)
                function = hir.ExpressedIdentifier(loc, signature, name, binding_id=binding.id)
                into.append(hir.FunctionCall(loc, ty.VOID_TYPE, function, arguments, {}))
                return
            if isinstance(shape, ty.ArrayType) and extraction is not None:
                # The selected element transfers; the other elements retain
                # reverse-order cleanup. Saved selectors name the same slot
                # for both the return value and this cleanup traversal.
                declaration, cursor = capture(hir.ArrayLength(loc, 'int64', value), loc)
                zero = hir.Integer(loc, 'int64', t0.base10, 0)
                one = hir.Integer(loc, 'int64', t0.base10, 1)
                signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64'), ty.PosOrKwArg(None, 'int64')], [], None, 'bool')
                def comparison(name, right):
                    function = hir.ExpressedIdentifier(loc, signature, name)
                    return hir.FunctionCall(loc, 'bool', function, [cursor, right], {})
                element = hir.Index(loc, shape.element, value, cursor, None)
                # Group paths sharing an element before descending into its
                # fields. Every transferred component must be omitted once.
                groups = {}
                for route, moved in routes:
                    selector = route[0]
                    key = ('literal', selector.value) if isinstance(selector, hir.Integer) else ('saved', id(selector))
                    groups.setdefault(key, (selector, []))[1].append((route[1:], moved))
                selected_arms, other_calls = [], []
                for selector, selected_routes in groups.values():
                    selected_calls = []
                    drop(element, shape.element, ancestors | {id(shape)}, into=selected_calls,
                         extraction=selected_routes[0], additional=selected_routes[1:])
                    selected_arms.append(hir.IfArm(loc, ty.VOID_TYPE, comparison('__eq__', selector),
                                                  hir.Block(loc, ty.VOID_TYPE, selected_calls, True)))
                drop(element, shape.element, ancestors | {id(shape)}, into=other_calls)
                body = hir.Block(loc, ty.VOID_TYPE, [hir.Assign(loc, ty.VOID_TYPE, cursor, '-=', one),
                    hir.Flow(loc, ty.VOID_TYPE, selected_arms, hir.Block(loc, ty.VOID_TYPE, other_calls, True))], True)
                loop = hir.LoopArm(loc, ty.VOID_TYPE, comparison('__gt__', zero), body)
                into.extend([declaration, hir.Flow(loc, ty.VOID_TYPE, [loop])])
                return
            if isinstance(shape, ty.ArrayType):
                # One checked helper per array shape: its borrowed receiver
                # has a stable identity even for an outer array's element.
                # Reuse also avoids duplicating nested cleanup loops at exits.
                cache = array_drops if tail is None else array_suffixes
                cached = cache.get(id(shape))
                operation = cached[1] if cached is not None else next(
                    (operation for known, operation in cache.values() if known == shape), None)
                if operation is None:
                    name = f'__dewy_drop_array_{registry.next_id}'
                    binding = registry.allocate(object(), name, 'value', loc)
                    parameter = registry.allocate(object(), '__items', 'param', loc)
                    parameter.type = shape
                    parameters = [hir.Param(parameter.name, shape, binding_id=parameter.id, place=True)]
                    result_type = ty.VOID_TYPE
                    if tail is not None:
                        first = registry.allocate(object(), '__first', 'param', loc)
                        first.type = ty.RefinedType('int64', (ty.Proposition('self', '>=?', 0),))
                        before = registry.allocate(object(), '__before', 'param', loc)
                        before.type = ty.RefinedType('int64', (ty.Proposition('self', '=?', 0,
                            term=parameter.name, term_id=parameter.id, term_of='length'),))
                        parameters.extend([hir.Param(first.name, first.type, binding_id=first.id),
                                           hir.Param(before.name, before.type, binding_id=before.id)])
                        result_type = ty.RefinedType(ty.VOID_TYPE, (ty.Proposition('@' + parameter.name, '=?', 0,
                            of='length', subject_id=parameter.id, term=before.name, term_id=before.id, term_of='value'),))
                    signature = ty.FunctionType([ty.PosOrKwArg(p.name, p.type, place=p.place) for p in parameters], [], None, result_type)
                    binding.type = signature
                    operation = hir.ExpressedIdentifier(loc, signature, name, binding_id=binding.id)
                    receiver = hir.ExpressedIdentifier(loc, shape, parameter.name, binding_id=parameter.id)
                    declaration, cursor = capture(hir.ArrayLength(loc, 'int64', receiver), loc)
                    zero = hir.Integer(loc, 'int64', t0.base10, 0)
                    one = hir.Integer(loc, 'int64', t0.base10, 1)
                    comparison = hir.ExpressedIdentifier(loc, ty.FunctionType(
                        [ty.PosOrKwArg(None, 'int64'), ty.PosOrKwArg(None, 'int64')], [], None, 'bool'), '__gt__')
                    limit = zero if tail is None else hir.ExpressedIdentifier(loc, first.type, first.name, binding_id=first.id)
                    condition = hir.FunctionCall(loc, 'bool', comparison, [cursor, limit], {})
                    element_calls = []
                    drop(hir.Index(loc, shape.element, receiver, cursor, None), shape.element, ancestors | {id(shape)}, into=element_calls)
                    body = hir.Block(loc, ty.VOID_TYPE, [hir.Assign(loc, ty.VOID_TYPE, cursor, '-=', one), *element_calls], True)
                    loop = hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(loc, ty.VOID_TYPE, condition, body)])
                    statements = [declaration, loop]
                    if tail is not None:
                        statements.append(hir.Obligation(loc, ty.VOID_TYPE, hir.Void(loc, ty.VOID_TYPE),
                            result_type, 'the generated suffix cleanup preserves length'))
                    literal = hir.FunctionLiteral(loc, signature, parameters, [], None,
                                                  ty.VOID_TYPE, hir.Block(loc, ty.VOID_TYPE, statements, True), source=current_source)
                    declared = hir.Declare(loc, ty.VOID_TYPE, 'const', name, signature, literal, binding_id=binding.id)
                    binding.function = literal
                    binding.declaration = declared
                    generated.append(declared)
                cache[id(shape)] = (shape, operation)
                arguments = [hir.Place(loc, shape, value), *(tail or ())]
                into.append(hir.FunctionCall(loc, ty.VOID_TYPE, replace(operation, loc=loc), arguments, {}))
                return
            if isinstance(shape, ty.TypeOr):
                # The tag selects the only live owner. A narrowed read keeps
                # the original storage identity; it does not copy its payload.
                arms = []
                for member in shape.items:
                    if resource(member) is None:
                        continue
                    member_shape = ty.structural_base(member)
                    if not run_hook and not (isinstance(member_shape, ty.ObjectType)
                                             and any(method.lifecycle == 'move' for method in member_shape.methods)):
                        # A different alternative moved intact; its nested
                        # resources now belong to the destination too.
                        continue
                    calls = []
                    drop(replace(value, type=member), member, ancestors | {id(shape)}, run_hook, into=calls, extraction=extraction, additional=additional)
                    condition = hir.TypeTest(loc, 'bool', value, member, False)
                    arms.append(hir.IfArm(loc, ty.VOID_TYPE, condition, hir.Block(loc, ty.VOID_TYPE, calls, True)))
                if arms:
                    into.append(hir.Flow(loc, ty.VOID_TYPE, arms, None))
                return
            if not isinstance(shape, ty.ObjectType):
                reject(value, 'unsupported resource storage')
            if ty.dict_key_value(shape) is not None:
                # Tombstones retain physical storage, but no logical owner.
                # Compact once before walking values; rebuilding already
                # releases dead backing storage without invoking hooks.
                into.append(compact_dictionary(value, shape, loc))
            hook = next((method for method in shape.methods if method.lifecycle == 'drop'), None)
            if hook is not None and run_hook:
                declaration = declarations.get(hook.binding_id)
                if declaration is None:
                    reject(value, 'an unavailable drop operation')
                function = hir.ExpressedIdentifier(loc, declaration.expr.type, declaration.name, binding_id=declaration.binding_id)
                into.append(hir.FunctionCall(loc, ty.VOID_TYPE, function, [hir.Place(loc, shape, value)], {}))
            # Parent body first; then fields in reverse declaration order.
            # Ordinary lowering releases the complete backing storage afterward.
            fields = shape.fields if run_hook else move_remainder(shape)
            for field in reversed(fields):
                if resource(field.type) is not None:
                    selected_routes = [(path[1:], moved) for path, moved in routes if path and path[0] == field.name]
                    nested = {path[1:]: flag for path, flag in (guards or {}).items() if path and path[0] == field.name}
                    drop(hir.MemberAccess(loc, field.type, value, field.name), field.type, ancestors | {id(shape)}, into=into,
                         extraction=selected_routes[0] if selected_routes else None, additional=selected_routes[1:],
                         guards=nested or None)
        for owner in reversed(owners):
            owner_type = owner.annotation or owner.expr.type
            value = hir.ExpressedIdentifier(loc, owner_type, owner.name, binding_id=owner.binding_id)
            calls = []
            routes = list(extractions.get(owner.binding_id, ()))
            if extracted is not None and extracted[0] == owner.binding_id:
                routes.append(extracted[1:])
            guards = {path: flag[1] for path, flag in component_flags.get(owner.binding_id, {}).items()}
            drop(value, owner_type, set(), owner.binding_id not in fields_only, into=calls,
                 extraction=routes[0] if routes else None, additional=routes[1:], guards=guards or None)
            flag = ownership_flags.get(owner.binding_id)
            if flag is not None and owner.binding_id not in fields_only:
                body = hir.Block(loc, ty.VOID_TYPE, calls, True)
                result.append(hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(loc, ty.VOID_TYPE, flag[1], body)], None))
            else:
                result.extend(calls)
        if selected is not None:
            # Replacing an ancestor of a moved component cleans only the
            # still-owned remainder. The new value then restores that route.
            part, path = selected, []
            while isinstance(part, hir.MemberAccess):
                path.append(part.name)
                part = part.value
            routes = []
            guards = {}
            if isinstance(part, hir.ExpressedIdentifier):
                path = tuple(reversed(path))
                existing = extractions.get(part.binding_id, ())
                routes = [(route[len(path):], moved) for route, moved in existing if route[:len(path)] == path]
                extractions[part.binding_id] = [(route, moved) for route, moved in existing if route[:len(path)] != path]
                guards = {route[len(path):]: flag[1] for route, flag in component_flags.get(part.binding_id, {}).items()
                          if route[:len(path)] == path}
            drop(selected, selected.type, set(), extraction=routes[0] if routes else None, additional=routes[1:],
                 guards=guards or None)
        if suffix is not None:
            value, first, before = suffix
            drop(value, value.type, set(), tail=(first, before))
        return result

    def returning_projection(value, owners):
        """An exiting owner may surrender a component through hook-free wrappers.

        A wrapper with lifecycle hooks still needs to see its complete value;
        ordinary synthesized wrappers can clean up their remaining fields.
        Borrowed parameters and aliases are not in the owning declaration set.
        """
        while isinstance(value, (hir.Obligation, hir.ValueCast, hir.RepresentationCast)):
            value = value.value if isinstance(value, hir.Obligation) else value.expr
        path = []
        while isinstance(value, (hir.MemberAccess, hir.Index)):
            if isinstance(value, hir.MemberAccess):
                shape = ty.structural_base(value.value.type)
                if not isinstance(shape, ty.ObjectType) or any(m.lifecycle is not None for m in shape.methods):
                    return None
                path.append(value.name)
                value = value.value
            else:
                path.append(value.index)
                value = value.array
        if (path and isinstance(value, hir.ExpressedIdentifier)
                and any(owner.binding_id == value.binding_id for owner in owners)):
            return value.binding_id, tuple(reversed(path))
        return None

    def transfer(value, expected):
        shape = ty.structural_base(value.type)
        if isinstance(shape, ty.TypeOr):
            arms = []
            for member in shape.items:
                selected = replace(value, type=member)
                result, moved = transfer(selected, member)
                if moved:
                    condition = hir.TypeTest(value.loc, 'bool', value, member, False)
                    arms.append(hir.IfArm(value.loc, result.type, condition, result))
            if not arms:
                return value, False
            result = hir.Flow(value.loc, value.type, arms, value)
            if isinstance(expected, ty.RefinedType):
                result = hir.Obligation(value.loc, value.type, result, expected, 'the return contract after moving')
            return result, True
        if not isinstance(shape, ty.ObjectType):
            return value, False
        hook = next((method for method in shape.methods if method.lifecycle == 'move'), None)
        if hook is None:
            return value, False
        operation = declarations.get(hook.binding_id)
        if operation is None:
            reject(value, 'an unavailable move operation')
        result_type = operation.expr.rettype
        if ty.structural_base(result_type) != shape:
            reject(value, 'an adapted move receiver without a checked composition')
        function = hir.ExpressedIdentifier(value.loc, operation.expr.type, operation.name, binding_id=operation.binding_id)
        result = hir.FunctionCall(value.loc, result_type, function, [hir.Place(value.loc, shape, value)], {})
        if isinstance(expected, ty.RefinedType):
            # The old value's facts are not facts about a hook's new result.
            result = hir.Obligation(value.loc, result_type, result, expected, 'the return contract after moving')
        return result, True

    def copy_operation(shape, loc):
        """A synthesized copy calls component hooks through checked HIR.

        Borrow once at the boundary, including for indexed receivers. The
        helper constructs a complete independent result; physical COW cannot
        substitute for a component's logical copy operation.
        """
        if isinstance(shape, ty.ObjectType):
            hook = next((method for method in shape.methods if method.lifecycle == 'copy'), None)
            if hook is not None:
                operation = declarations.get(hook.binding_id)
                if operation is None:
                    reject(root, 'an unavailable copy operation')
                return hir.ExpressedIdentifier(loc, operation.expr.type, operation.name, binding_id=operation.binding_id)
        cached = component_copies.get(id(shape))
        operation = cached[1] if cached is not None else next(
            (operation for known, operation in component_copies.values() if known == shape), None)
        if operation is not None:
            return replace(operation, loc=loc)
        if not isinstance(shape, (ty.ObjectType, ty.TypeOr, ty.ArrayType)):
            reject(root, 'synthesized copies of this resource container')
        name = f'__dewy_copy_components_{registry.next_id}'
        binding = registry.allocate(object(), name, 'value', loc)
        parameter = registry.allocate(object(), '__source', 'param', loc)
        parameter.type = shape
        result_type = ty.RefinedType(shape, (ty.Proposition('length', '=?', 0,
            term='__source', term_id=parameter.id),)) if isinstance(shape, ty.ArrayType) else shape
        signature = ty.FunctionType([ty.PosOrKwArg('__source', shape, place=True)], [], None, result_type)
        binding.type = signature
        operation = hir.ExpressedIdentifier(loc, signature, name, binding_id=binding.id)
        component_copies[id(shape)] = (shape, operation)
        receiver = hir.ExpressedIdentifier(loc, shape, parameter.name, binding_id=parameter.id)
        prefix = []
        if isinstance(shape, ty.ArrayType):
            dynamic = ty.ArrayType(shape.element, None)
            output = registry.allocate(object(), '__result', 'value', loc)
            output.type = dynamic
            empty = hir.ArrayLiteral(loc, ty.ArrayType(shape.element, 0), [])
            declaration = hir.Declare(loc, ty.VOID_TYPE, 'let', output.name, dynamic, empty, binding_id=output.id)
            output.declaration = declaration
            value = hir.ExpressedIdentifier(loc, dynamic, output.name, binding_id=output.id)
            zero = hir.Integer(loc, 'int64', t0.base10, 0)
            one = hir.Integer(loc, 'int64', t0.base10, 1)
            cursor_decl, cursor = capture(zero, loc)
            comparison = hir.ExpressedIdentifier(loc, ty.FunctionType(
                [ty.PosOrKwArg(None, 'int64'), ty.PosOrKwArg(None, 'int64')], [], None, 'bool'), '__lt__')
            condition = hir.FunctionCall(loc, 'bool', comparison, [cursor, hir.ArrayLength(loc, 'int64', receiver)], {})
            element = copy_value(hir.Index(loc, shape.element, receiver, cursor, None), implicit=False)
            push_type = ty.FunctionType([ty.PosOrKwArg('value', shape.element)], [], None, ty.VOID_TYPE)
            push = hir.FunctionCall(loc, ty.VOID_TYPE, hir.ArrayMethod(loc, push_type, value, 'push'), [element], {})
            loop_body = hir.Block(loc, ty.VOID_TYPE, [push, hir.Assign(loc, ty.VOID_TYPE, cursor, '+=', one)], True)
            loop = hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(loc, ty.VOID_TYPE, condition, loop_body)])
            prefix = [declaration, cursor_decl, loop]
            # Both dynamic and fixed-size results owe the source's length.
            # The ordinary loop proof, not synthesized metadata, establishes it.
            value = hir.Obligation(loc, shape, value, result_type, 'the generated array copy return contract')
        elif isinstance(shape, ty.ObjectType):
            if ty.dict_key_value(shape) is not None:
                prefix.append(compact_dictionary(receiver, shape, loc))
            value = hir.ObjectLiteral(loc, shape, [hir.ObjectField(loc, field.name,
                copy_value(hir.MemberAccess(loc, field.type, receiver, field.name), implicit=False))
                for field in shape.fields])
        else:
            alternatives = []
            for member in shape.items:
                selected = copy_value(replace(receiver, type=member), implicit=False)
                selected = hir.ValueCast(loc, shape, selected)
                alternatives.append((member, selected))
            value = hir.Flow(loc, shape, [hir.IfArm(loc, shape,
                hir.TypeTest(loc, 'bool', receiver, member, False), result)
                for member, result in alternatives[:-1]], alternatives[-1][1])
        body = hir.Block(loc, ty.BOTTOM_TYPE, [*prefix, hir.Return(loc, ty.BOTTOM_TYPE, value)], True)
        literal = hir.FunctionLiteral(loc, signature,
            [hir.Param(parameter.name, shape, binding_id=parameter.id, place=True)], [], None,
            shape, body, source=current_source)
        declared = hir.Declare(loc, ty.VOID_TYPE, 'const', name, signature, literal, binding_id=binding.id)
        binding.function = literal
        binding.declaration = declared
        generated.append(declared)
        return operation

    def copy_value(value, *, implicit):
        if resource(value.type) is None:
            shape = ty.structural_base(value.type)
            return hir.CopyValue(value.loc, value.type, value) if isinstance(shape, (ty.ArrayType, ty.ObjectType, ty.TypeOr)) or ty.string_valued(shape) else value
        if lifecycle.copy_blocker(value.type) is not None:
            user_error(current_source, 'lifecycle ownership lowering requires an independent copy',
                       Pointer(span=value.loc, message='this move-only value is still owned elsewhere'),
                       hint='declare $__copy__ for independent owners, or keep this use within a proven borrow or last-use transfer')
        shape = ty.structural_base(value.type)
        operation = copy_operation(shape, value.loc)
        result = hir.FunctionCall(value.loc, operation.type.ret, operation,
                                  [hir.Place(value.loc, shape, value)], {}, implicit_copy=implicit)
        if isinstance(value.type, ty.RefinedType):
            result = hir.Obligation(value.loc, result.type, result, value.type, 'the value contract after copying')
        return result

    def fresh(node, allowed, inherited, components=frozenset(), control=None):
        if resource(node.type) is None:
            return expression(node, allowed, inherited=inherited, control=control)
        if isinstance(node, hir.DictView):
            return dictionary_view(node, allowed, inherited, control)
        if isinstance(node, hir.DictLookup) and not node.proven:
            return dictionary_get(node, allowed, inherited, control)
        if isinstance(node, hir.DictRemove) and node.key is not None:
            return dictionary_pop(node, allowed, inherited, control)
        if isinstance(node, (hir.ExpressedIdentifier, hir.MemberAccess, hir.Index)) and control is not None:
            consumed = control(node, consume=True)
            if consumed is not None:
                return consumed
        if isinstance(node, (hir.Block, hir.Flow)) and control is not None:
            # Each arm supplies an independent owner. Its scoped temporaries
            # must be cleaned up after capturing that arm's expressed value.
            return control(node, fresh_result=True)
        if isinstance(node, hir.Obligation):
            return replace(node, value=fresh(node.value, allowed, inherited, components, control))
        if isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
            target = ty.structural_base(node.type)
            source = ty.structural_base(node.expr.type)
            if isinstance(target, ty.TypeOr) or source == target:
                # Naming the same storage through a recursive alias does not
                # change whether the underlying constructor is fresh.
                return replace(node, expr=fresh(node.expr, allowed, inherited, components, control))
        if isinstance(node, hir.MemberAccess):
            owner = node.value
            while isinstance(owner, hir.MemberAccess):
                owner = owner.value
            if isinstance(owner, hir.ExpressedIdentifier) and owner.binding_id in components:
                # The checked inheritance wrapper transfers every parent
                # field into its complete child, consuming that intermediate.
                return node
        if isinstance(node, (hir.ExpressedIdentifier, hir.MemberAccess, hir.Index)) or isinstance(node, hir.DictLookup) and node.proven:
            receiver = expression(hir.Place(node.loc, node.type, node), allowed,
                                  inherited=inherited, control=control)
            return copy_value(receiver.target, implicit=True)
        if isinstance(node, hir.CopyValue):
            if isinstance(node.value, (hir.ExpressedIdentifier, hir.MemberAccess, hir.Index)) or isinstance(node.value, hir.DictLookup) and node.value.proven:
                receiver = expression(hir.Place(node.loc, node.value.type, node.value), allowed,
                                      inherited=inherited, control=control)
                return copy_value(receiver.target, implicit=False)
            owner, borrowed = capture(fresh(node.value, allowed, inherited, control=control), node.loc)
            copied, result = capture(copy_value(borrowed, implicit=False), node.loc)
            return hir.Block(node.loc, node.type, [owner, copied, *cleanup([owner], node.loc), result], False)
        # An explicit custom copy creates an independent owner. Its checked
        # call already carries the hook's effects and result contract.
        if isinstance(node, hir.FunctionCall):
            if isinstance(node.func, hir.ArrayMethod) and resource(node.func.array.type) is not None:
                return array_operation(node, allowed, inherited, control)
            operation = declarations.get(node.func.binding_id) if isinstance(node.func, hir.ExpressedIdentifier) else None
            if operation is not None and operation.expr.lifecycle == 'copy':
                if len(node.pos_args) != 1 or node.kw_args or not isinstance(node.pos_args[0], hir.Place):
                    reject(node, 'an invalid copy receiver')
                receiver = node.pos_args[0].target
                if isinstance(receiver, (hir.FunctionCall, hir.ObjectLiteral)):
                    # A temporary receiver owns its resource until the copy
                    # finishes. Snapshot the result before dropping that
                    # receiver; neither evaluation nor cleanup is duplicated.
                    owner, borrowed = capture(fresh(receiver, allowed, inherited, control=control), node.loc)
                    copied = replace(node, pos_args=[replace(node.pos_args[0], target=borrowed)])
                    result, value = capture(copied, node.loc)
                    return hir.Block(node.loc, node.type, [owner, result, *cleanup([owner], node.loc), value], False)
                borrowed = expression(node.pos_args[0], allowed, inherited=inherited, control=control)
                return replace(node, pos_args=[borrowed])
            # A function result is an owned value, including through a
            # callback. Every checked body owes the same return contract;
            # resource arguments still require their own ownership proof.
            return replace(node, func=expression(node.func, allowed, inherited=inherited, control=control),
                           pos_args=[argument(arg, allowed, inherited, control) for arg in node.pos_args],
                           kw_args={name: argument(arg, allowed, inherited, control) for name, arg in node.kw_args.items()})
        shape = ty.structural_base(node.type)
        if isinstance(node, hir.ArrayLiteral) and isinstance(shape, ty.ArrayType):
            return replace(node, items=[fresh(item, allowed, inherited, components, control) for item in node.items])
        if not isinstance(node, hir.ObjectLiteral) or not isinstance(shape, ty.ObjectType):
            reject(node, 'a non-fresh resource field or resource container')
        hook = next((method for method in shape.methods if method.lifecycle == 'drop'), None)
        if hook is not None:
            operation = declarations.get(hook.binding_id)
            if operation is None or ty.structural_base(operation.expr.pos_or_kw_args[0].type) != shape:
                reject(node, 'an adapted drop receiver without a checked composition')
        return replace(node, fields=[replace(field, value=fresh(field.value, allowed, inherited, components, control)
                                            if resource(field.value.type) is not None else expression(field.value, allowed, inherited=inherited, control=control))
                                     for field in node.fields])

    def capture(value, loc):
        # Evaluate the result before cleanup. Ordinary lowering transfers a
        # fresh aggregate or snapshots a borrowed field that drop may mutate.
        name = f'__dewy_drop_result_{registry.next_id}'
        binding = registry.allocate(object(), name, 'value', loc)
        binding.type = value.type
        declaration = hir.Declare(loc, ty.VOID_TYPE, 'let', name, value.type, value, binding_id=binding.id)
        binding.declaration = declaration
        return declaration, hir.ExpressedIdentifier(loc, value.type, name, binding_id=binding.id)

    def mapped(value, visit):
        if isinstance(value, hir.AST):
            return visit(value)
        if isinstance(value, list):
            return [mapped(item, visit) for item in value]
        if isinstance(value, tuple):
            return tuple(mapped(item, visit) for item in value)
        if isinstance(value, dict):
            return {key: mapped(item, visit) for key, item in value.items()}
        if isinstance(value, (hir.ObjectField, hir.Param)):
            return replace(value, **{name: mapped(getattr(value, name), visit) for name in hir.child_fields(type(value))})
        return value

    def argument(node, allowed, inherited, control=None):
        # A fresh value (including an explicit custom copy) supplies a new
        # owner to an ordinary by-value parameter. @ keeps lending the owner.
        if not isinstance(node, hir.Place) and resource(node.type) is not None:
            return fresh(node, allowed, inherited, control=control)
        return expression(node, allowed, inherited=inherited, control=control)

    def route_indices(node, allowed, inherited, control):
        if isinstance(node, hir.DictLookup) and node.proven:
            owner = route_indices(node.keys.value, allowed, inherited, control)
            return replace(node, keys=replace(node.keys, value=owner), values=replace(node.values, value=owner),
                           key=expression(node.key, allowed, inherited=inherited, control=control))
        # Hosted HIR is immutable-by-replacement: retain rewritten control
        # flow in a selector, not just its successful validation.
        if isinstance(node, hir.MemberAccess):
            return replace(node, value=route_indices(node.value, allowed, inherited, control))
        if isinstance(node, hir.Index):
            return replace(node, array=route_indices(node.array, allowed, inherited, control),
                           index=expression(node.index, allowed, inherited=inherited, control=control))
        return node

    def clear_operation(shape, loc):
        cached = array_clears.get(id(shape))
        operation = cached[1] if cached is not None else next(
            (operation for known, operation in array_clears.values() if known == shape), None)
        if operation is None:
            name = f'__dewy_clear_array_{registry.next_id}'
            binding = registry.allocate(object(), name, 'value', loc)
            parameter = registry.allocate(object(), '__items', 'param', loc)
            parameter.type = shape
            # A normal checked return fact retains the builtin's length
            # guarantee, even though element drop is now a helper call.
            result = ty.RefinedType(ty.VOID_TYPE, (ty.Proposition(
                '@__items', '=?', 0, of='length', subject_id=parameter.id),))
            signature = ty.FunctionType([ty.PosOrKwArg('__items', shape, place=True)], [], None, result)
            binding.type = signature
            operation = hir.ExpressedIdentifier(loc, signature, name, binding_id=binding.id)
            receiver = hir.ExpressedIdentifier(loc, shape, parameter.name, binding_id=parameter.id)
            borrowed = hir.Declare(loc, ty.VOID_TYPE, 'let', parameter.name, shape, receiver, binding_id=parameter.id)
            method_type = ty.FunctionType([], [], None, ty.VOID_TYPE)
            method = hir.ArrayMethod(loc, method_type, receiver, 'clear')
            clear = hir.FunctionCall(loc, ty.VOID_TYPE, method, [], {})
            # Generated signatures bypass source return checking. Materialize
            # the same obligation explicitly; the signature alone is no proof.
            verified = hir.Obligation(loc, ty.VOID_TYPE, hir.Void(loc, ty.VOID_TYPE),
                                      result, 'the generated clear return contract')
            body = hir.Block(loc, ty.VOID_TYPE, [*cleanup([borrowed], loc), clear, verified], True)
            literal = hir.FunctionLiteral(loc, signature,
                [hir.Param(parameter.name, shape, binding_id=parameter.id, place=True)],
                [], None, ty.VOID_TYPE, body, source=current_source)
            declared = hir.Declare(loc, ty.VOID_TYPE, 'const', name, signature, literal, binding_id=binding.id)
            binding.function = literal
            binding.declaration = declared
            generated.append(declared)
        array_clears[id(shape)] = (shape, operation)
        return replace(operation, loc=loc)

    def check_selection(value, root_id):
        writes = predicate_effects.mutated_bindings(value, call_writes=argument_writes,
                                                   read_only_places=readonly_arguments)
        if root_id in writes:
            user_error(current_source, 'resource receiver changes during evaluation',
                       Pointer(span=value.loc, message='the selected storage must survive its selectors and arguments'))

    def freeze_value(value, loc, prefix):
        # Literals already denote stable selectors; retaining them also keeps
        # equal constant indices recognizable across independent transfers.
        if isinstance(value, hir.Integer):
            return value
        declaration, held = capture(value, loc)
        declaration = replace(declaration, decltype='const')
        registry.by_id[held.binding_id].declaration = declaration
        prefix.append(declaration)
        return held

    def freeze_route(value, loc, root_id, prefix):
        # Preserve the rooted place, capturing only selectors. A raw pointer
        # could become stale when mutable-place lowering detaches COW storage.
        if isinstance(value, hir.Obligation):
            return replace(value, value=freeze_route(value.value, loc, root_id, prefix))
        if isinstance(value, (hir.ValueCast, hir.RepresentationCast)):
            return replace(value, expr=freeze_route(value.expr, loc, root_id, prefix))
        if isinstance(value, hir.MemberAccess):
            return replace(value, value=freeze_route(value.value, loc, root_id, prefix))
        if isinstance(value, hir.Index):
            array = freeze_route(value.array, loc, root_id, prefix)
            check_selection(value.index, root_id)
            return replace(value, array=array, index=freeze_value(value.index, loc, prefix))
        if isinstance(value, hir.DictLookup) and value.proven:
            # Cleanup and the eventual mutation share one captured key and
            # receiver. Their physical positions may change during cleanup.
            assert isinstance(value.keys, hir.MemberAccess) and isinstance(value.values, hir.MemberAccess)
            owner = freeze_route(value.keys.value, loc, root_id, prefix)
            check_selection(value.key, root_id)
            key = freeze_value(value.key, loc, prefix)
            return replace(value, keys=replace(value.keys, value=owner),
                           values=replace(value.values, value=owner), key=key,
                           position=None, static_position=None)
        return value

    def array_operation(node, allowed, inherited, control):
        method = node.func
        if method.name not in ('push', 'insert', 'pop', 'reserve', 'clear', 'truncate'):
            reject(node, 'a resource array method without element lifetime handling')
        # Borrow the receiver once. Clearing uses a checked helper to drop
        # live elements; insertion/removal otherwise transfers their owners.
        receiver = expression(hir.Place(method.loc, method.array.type, method.array), allowed,
                              inherited=inherited, control=control)
        if method.name == 'truncate':
            prefix = []
            receiver_root = bindings.access_path(receiver.target, dictionaries=True).binding_id
            selected = freeze_route(receiver.target, node.loc, receiver_root, prefix)
            supplied = node.pos_args[0] if node.pos_args else node.kw_args['count']
            check_selection(supplied, receiver_root)
            count = freeze_value(expression(supplied, allowed, inherited=inherited, control=control), node.loc, prefix)
            before = freeze_value(hir.ArrayLength(node.loc, 'int64', selected), node.loc, prefix)
            dropped = cleanup((), node.loc, suffix=(selected, count, before))
            truncated = replace(node, func=replace(method, array=selected), pos_args=[count], kw_args={})
            return hir.Block(node.loc, node.type, [*prefix, *dropped, truncated], False)
        if method.name == 'clear':
            shape = ty.structural_base(method.array.type)
            assert isinstance(shape, ty.ArrayType)
            return hir.FunctionCall(node.loc, ty.VOID_TYPE, clear_operation(shape, node.loc), [receiver], {})
        return replace(node, func=replace(method, array=receiver.target),
                       pos_args=[argument(arg, allowed, inherited, control) for arg in node.pos_args],
                       kw_args={name: argument(arg, allowed, inherited, control) for name, arg in node.kw_args.items()})

    def compact_dictionary(value, shape, loc):
        # DictEntries is the existing representation operation for obtaining
        # insertion-ordered live storage. Suppressing its borrowed descriptor
        # only requests compaction; it creates no independent resource array.
        field = shape.field('values')
        assert field is not None
        entries = hir.DictEntries(loc, field.type, value, 'values')
        return hir.Suppress(loc, ty.VOID_TYPE, entries)

    def dictionary_clear(node, allowed, inherited, control):
        # Dictionary bookkeeping still belongs to DictRemove. Run checked
        # element cleanup first, then let it release storage and reset the
        # table. Freeze the shared dictionary route once for both fields.
        if not isinstance(node.keys, hir.MemberAccess) or not isinstance(node.values, hir.MemberAccess):
            reject(node, 'a dictionary clear without rooted storage')
        owner = node.keys.value
        borrowed = expression(hir.Place(node.loc, owner.type, owner), allowed,
                              inherited=inherited, control=control)
        prefix = []
        selected = freeze_route(borrowed.target, node.loc, bindings.access_path(owner, dictionaries=True).binding_id, prefix)
        keys = replace(node.keys, value=selected)
        values = replace(node.values, value=selected)
        return hir.Block(node.loc, node.type, [*prefix, *cleanup((), node.loc, selected=selected),
                                              replace(node, keys=keys, values=values)], False)

    def dictionary_view(node, allowed, inherited, control):
        owner = expression(hir.Place(node.loc, node.dictionary.type, node.dictionary), allowed,
                           inherited=inherited, control=control).target
        shape = ty.structural_base(owner.type)
        assert isinstance(shape, ty.ObjectType)
        prefix = []
        selected = freeze_route(owner, node.loc, bindings.access_path(owner, dictionaries=True).binding_id, prefix)
        if resource(node.type) is None:
            return hir.Block(node.loc, node.type, [*prefix, replace(node, dictionary=selected)], False)
        # The public values view owns independent elements. Compact before
        # copying so tombstones never trigger component hooks.
        field = shape.field(node.name)
        assert field is not None
        values = hir.MemberAccess(node.loc, field.type, selected, field.name)
        return hir.Block(node.loc, node.type, [*prefix, compact_dictionary(selected, shape, node.loc),
                                               copy_value(values, implicit=True)], False)

    def dictionary_pop(node, allowed, inherited, control):
        assert isinstance(node.keys, hir.MemberAccess) and isinstance(node.values, hir.MemberAccess)
        owner = node.keys.value
        expression(hir.Place(node.loc, owner.type, owner), allowed, inherited=inherited, control=control)
        prefix = []
        root_id = bindings.access_path(owner, dictionaries=True).binding_id
        selected = freeze_route(owner, node.loc, root_id, prefix)
        check_selection(node.key, root_id)
        key = freeze_value(expression(node.key, allowed, inherited=inherited, control=control), node.loc, prefix)
        default_owner = None
        fallback = None
        if node.default is not None:
            check_selection(node.default, root_id)
            default_owner, fallback = capture(fresh(node.default, allowed, inherited, control=control), node.loc)
            prefix.append(default_owner)
        keys, values = replace(node.keys, value=selected), replace(node.values, value=selected)
        shape = ty.structural_base(values.type)
        assert isinstance(shape, ty.ArrayType)
        removed = replace(node, type=shape.element, keys=keys, values=values, key=key,
                          default=None, position=None, static_position=None)
        held, result = capture(removed, node.loc)
        taken = hir.Block(node.loc, node.type, [held,
            *cleanup([default_owner] if default_owner is not None else [], node.loc),
            hir.ValueCast(node.loc, node.type, result)], False)
        if fallback is not None:
            condition = hir.DictContains(node.loc, 'bool', keys, key)
            taken = hir.Flow(node.loc, node.type, [hir.IfArm(node.loc, node.type, condition, taken)],
                             hir.ValueCast(node.loc, node.type, fallback))
        return hir.Block(node.loc, node.type, [*prefix, taken], False)

    def dictionary_get(node, allowed, inherited, control):
        # A default is eagerly evaluated, even when the entry exists. Each
        # path owns exactly one result; the found path drops its unused default.
        assert isinstance(node.keys, hir.MemberAccess) and isinstance(node.values, hir.MemberAccess)
        owner = node.keys.value
        expression(hir.Place(node.loc, owner.type, owner), allowed, inherited=inherited, control=control)
        prefix = []
        root_id = bindings.access_path(owner, dictionaries=True).binding_id
        selected = freeze_route(owner, node.loc, root_id, prefix)
        check_selection(node.key, root_id)
        key = freeze_value(expression(node.key, allowed, inherited=inherited, control=control), node.loc, prefix)
        default_owner = None
        fallback = hir.NoneValue(node.loc, 'none')
        if node.default is not None:
            check_selection(node.default, root_id)
            default_owner, fallback = capture(fresh(node.default, allowed, inherited, control=control), node.loc)
            prefix.append(default_owner)
        keys, values = replace(node.keys, value=selected), replace(node.values, value=selected)
        shape = ty.structural_base(values.type)
        assert isinstance(shape, ty.ArrayType)
        found = hir.DictLookup(node.loc, shape.element, keys, values, key, proven=True)
        copied, result = capture(copy_value(found, implicit=True), node.loc)
        taken = hir.Block(node.loc, node.type, [copied,
            *cleanup([default_owner] if default_owner is not None else [], node.loc),
            hir.ValueCast(node.loc, node.type, result)], False)
        condition = hir.DictContains(node.loc, 'bool', keys, key)
        flow = hir.Flow(node.loc, node.type, [hir.IfArm(node.loc, node.type, condition, taken)],
                        hir.ValueCast(node.loc, node.type, fallback))
        return hir.Block(node.loc, node.type, [*prefix, flow], False)

    def dictionary_store(node, allowed, inherited, control):
        # Evaluate receiver selectors, key and replacement before dropping
        # the old owner. Ordinary dictionary lowering still owns hashing,
        # growth and physical storage release.
        assert isinstance(node.keys, hir.MemberAccess) and isinstance(node.values, hir.MemberAccess)
        owner = node.keys.value
        expression(hir.Place(node.loc, owner.type, owner), allowed, inherited=inherited, control=control)
        prefix = []
        root_id = bindings.access_path(owner, dictionaries=True).binding_id
        selected = freeze_route(owner, node.loc, root_id, prefix)
        for supplied in (node.key, node.value):
            check_selection(supplied, root_id)
        key = freeze_value(expression(node.key, allowed, inherited=inherited, control=control), node.loc, prefix)
        value = freeze_value(fresh(node.value, allowed, inherited, control=control), node.loc, prefix)
        keys, values = replace(node.keys, value=selected), replace(node.values, value=selected)
        shape = ty.structural_base(values.type)
        assert isinstance(shape, ty.ArrayType)
        previous = hir.DictLookup(node.loc, shape.element, keys, values, key, proven=True)
        calls = cleanup((), node.loc, selected=previous)
        condition = hir.DictContains(node.loc, 'bool', keys, key)
        drop = hir.Flow(node.loc, ty.VOID_TYPE, [hir.IfArm(node.loc, ty.VOID_TYPE, condition,
                        hir.Block(node.loc, ty.VOID_TYPE, calls, True))])
        return hir.Block(node.loc, node.type, [*prefix, drop,
                         replace(node, keys=keys, values=values, key=key, value=value)], False)

    def expression(node, allowed, *, inherited=False, control=None):
        if isinstance(node, hir.DictView) and resource(node.dictionary.type) is not None:
            return dictionary_view(node, allowed, inherited, control)
        if isinstance(node, hir.DictEntries) and resource(node.dictionary.type) is not None:
            receiver = expression(hir.Place(node.loc, node.dictionary.type, node.dictionary), allowed,
                                  inherited=inherited, control=control)
            return replace(node, dictionary=receiver.target)
        if isinstance(node, hir.IteratorExpression) and node.target.binding_id in iteration_loans:
            if isinstance(node.iterable, hir.DictEntries):
                iterable = expression(node.iterable, allowed, inherited=inherited, control=control)
            else:
                iterable = expression(hir.Place(node.loc, node.iterable.type, node.iterable), allowed,
                                      inherited=inherited, control=control).target
            return replace(node, iterable=iterable)
        if isinstance(node, hir.DictStore) and node.values is not None and resource(node.values.type) is not None:
            return dictionary_store(node, allowed, inherited, control)
        if (isinstance(node, hir.DictRemove) and node.key is None and node.values is not None
                and resource(node.values.type) is not None):
            return dictionary_clear(node, allowed, inherited, control)
        if control is not None and isinstance(node, (hir.Block, hir.Flow, hir.Return, hir.Break, hir.Continue, hir.OrThrow)):
            return control(node)
        if isinstance(node, hir.Suppress) and resource(node.item.type) is not None:
            owner, _value = capture(fresh(node.item, allowed, inherited, control=control), node.loc)
            return hir.Block(node.loc, ty.VOID_TYPE, [owner, *cleanup([owner], node.loc)], False)
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod) and resource(node.func.array.type) is not None:
            return array_operation(node, allowed, inherited, control)
        if isinstance(node, hir.FunctionLiteral):
            return function(node)
        if (isinstance(node, hir.TypeValue)
                or isinstance(node, hir.FunctionCall) and node.proof
                or isinstance(node, hir.Assert) and not node.runtime and not node.expect):
            return node
        if (isinstance(node, (hir.MemberAccess, hir.ForwardingAccess)) and resource(node.value.type) is not None
                or isinstance(node, hir.ArrayLength) and resource(node.array.type) is not None):
            selected = route_indices(node.value if isinstance(node, (hir.MemberAccess, hir.ForwardingAccess)) else node.array, allowed, inherited, control)
            owner = selected
            while isinstance(owner, (hir.MemberAccess, hir.Index, hir.DictLookup)):
                if isinstance(owner, hir.DictLookup):
                    owner = owner.keys.value
                elif isinstance(owner, hir.Index):
                    owner = owner.array
                else:
                    owner = owner.value
            if (not isinstance(owner, hir.ExpressedIdentifier) or owner.binding_id not in allowed
                    or resource(node.type) is not None):
                reject(node, 'an escaping or projected resource owner')
            return replace(node, **({'value': selected} if isinstance(node, (hir.MemberAccess, hir.ForwardingAccess)) else {'array': selected}))
        if isinstance(node, hir.TypeTest) and resource(node.value.type) is not None:
            borrowed = expression(hir.Place(node.loc, node.value.type, node.value), allowed,
                                  inherited=inherited, control=control)
            return replace(node, value=borrowed.target)
        if isinstance(node, hir.FunctionCall) and inherited and isinstance(node.func, hir.ExpressedIdentifier) and node.func.binding_id in declarations:
            # The checker generated this parent-portion drop invocation.
            if len(node.pos_args) != 1 or not isinstance(node.pos_args[0], hir.Place):
                reject(node, 'an invalid inherited drop receiver')
            value = node.pos_args[0].target
            if not isinstance(value, hir.ExpressedIdentifier) or value.binding_id not in allowed:
                reject(node, 'an escaping inherited drop receiver')
            return node
        if isinstance(node, hir.Place):
            selected = route_indices(node.target, allowed, inherited, control)
            path = selected
            while isinstance(path, (hir.MemberAccess, hir.Index, hir.DictLookup)):
                path = path.keys.value if isinstance(path, hir.DictLookup) else path.value if isinstance(path, hir.MemberAccess) else path.array
            if resource(path.type) is not None:
                # A checked place call borrows the existing owner. Its
                # lifetime and overlapping routes are checked by the normal
                # place rules; the callee must not acquire another owner.
                if not isinstance(path, hir.ExpressedIdentifier) or path.binding_id not in allowed:
                    reject(node, 'an unavailable resource borrow')
                return replace(node, target=selected)
        if isinstance(node, hir.FunctionCall) and resource(node.type) is None:
            return replace(node, func=expression(node.func, allowed, inherited=inherited, control=control),
                           pos_args=[argument(arg, allowed, inherited, control) for arg in node.pos_args],
                           kw_args={name: argument(arg, allowed, inherited, control) for name, arg in node.kw_args.items()})
        if resource(node.type) is not None:
            reject(node, 'a resource copy, move, temporary, or escape')
        return replace(node, **{name: mapped(getattr(node, name), lambda child: expression(child, allowed, inherited=inherited, control=control))
                                for name in hir.child_fields(type(node))})

    def local_transfers(body, parameter_owners, borrowed_parameters):
        """Prove same-scope transfers before introducing cleanup calls.

        Later branches count as uses, and captures prevent transfer. Owners
        declared outside a branch/loop are excluded by the same-block rule;
        their conditional consumption needs a separate lifetime join.
        """
        last, occurrences, captured, written = {}, {}, set(), set()
        def written_root(node):
            while isinstance(node, (hir.MemberAccess, hir.Index)):
                node = node.value if isinstance(node, hir.MemberAccess) else node.array
            if isinstance(node, hir.ExpressedIdentifier):
                written.add(node.binding_id)
        blocks = []
        lexical = {owner.binding_id for owner in parameter_owners} | iteration_loans | borrowed_parameters
        pending = [body]
        while pending:
            node = pending.pop()
            if isinstance(node, hir.FunctionLiteral):
                captured.update(child.binding_id for child in hir.walk(node)
                                if isinstance(child, hir.ExpressedIdentifier))
                continue
            if isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign, hir.Place)):
                written_root(node.target)
            if isinstance(node, hir.ArrayMethod):
                written_root(node.array)
            if isinstance(node, (hir.DictStore, hir.DictRemove)):
                written_root(node.keys)
            if isinstance(node, hir.Transmute):
                written_root(node.expr)
            if isinstance(node, hir.ExpressedIdentifier):
                last[node.binding_id] = id(node)
                occurrences[id(node)] = occurrences.get(id(node), 0) + 1
            if isinstance(node, hir.Block):
                blocks.append(node)
            if isinstance(node, hir.Declare):
                lexical.add(node.binding_id)
            pending.extend(reversed(tuple(hir.children(node))))
        read_routes, reads_by_binding = {}, {}
        pending = [(body, ())]
        while pending:
            node, route = pending.pop()
            if isinstance(node, hir.FunctionLiteral):
                continue
            if isinstance(node, hir.MemberAccess):
                pending.append((node.value, (node.name, *route)))
            elif isinstance(node, hir.Index) and isinstance(node.index, hir.Integer):
                pending.append((node.array, (node.index.value, *route)))
            else:
                if isinstance(node, hir.ExpressedIdentifier):
                    reads_by_binding.setdefault(node.binding_id, []).append(node)
                    read_routes[id(node)] = route if id(node) not in read_routes or read_routes[id(node)] == route else ()
                pending.extend((child, ()) for child in hir.children(node))
        result, views, consumes = set(), set(), set()
        # A lexical position is enough for this same-block proof. Dependent
        # read-only aliases keep their original owner live as well.
        positions = {read: index for index, read in enumerate(occurrences)}
        dependent, born = {}, {}
        for block in blocks:
            for node in block.items:
                if (isinstance(node, hir.Declare) and isinstance(node.expr, hir.ExpressedIdentifier)
                        and resource(node.expr.type) is not None
                        and not {node.binding_id, node.expr.binding_id} & (captured | written)):
                    dependent.setdefault(node.expr.binding_id, set()).add(node.binding_id)
                    born[node.binding_id] = positions[id(node.expr)]
        def alive_after(binding, read):
            pending = list(dependent.get(binding, ()))
            seen = set()
            while pending:
                alias = pending.pop()
                if alias in seen or born[alias] >= positions[read]:
                    continue
                seen.add(alias)
                if positions.get(last.get(alias), -1) > positions[read]:
                    return True
                pending.extend(dependent.get(alias, ()))
            return False
        # A direct replacement in this same block starts a new lifetime.
        # Its RHS still observes the old value: stop only after all reads in
        # that statement, exempting just the assignment's target occurrence.
        renewals = {}
        for block in blocks:
            for node in block.items:
                if not isinstance(node, (hir.Assign, hir.MemberAssign)) or isinstance(node, hir.Assign) and node.op != '=':
                    continue
                target, path = node.target, []
                while isinstance(target, hir.MemberAccess):
                    path.append(target.name)
                    target = target.value
                if not isinstance(target, hir.ExpressedIdentifier) or occurrences.get(id(target)) != 1:
                    continue
                end = max((positions[id(read)] for read in hir.walk(node)
                           if isinstance(read, hir.ExpressedIdentifier)), default=-1)
                renewals.setdefault((id(block), target.binding_id), []).append((id(target), tuple(reversed(path)), end))

        def last_component(value, owner, block):
            if isinstance(value, hir.ExpressedIdentifier):
                return last.get(owner.binding_id) == id(owner)
            # Record fields and constant array indices denote disjoint
            # components. Dynamic selectors still require a whole-root last
            # use; resizing or passing the array observes its entire route.
            part = value
            while isinstance(part, (hir.MemberAccess, hir.Index)):
                if isinstance(part, hir.Index):
                    if not isinstance(part.index, hir.Integer):
                        break
                    part = part.array
                else:
                    part = part.value
            if not isinstance(part, hir.ExpressedIdentifier):
                return last.get(owner.binding_id) == id(owner)
            route = read_routes[id(owner)]
            stop, target = None, None
            for write, path, end in renewals.get((id(block), owner.binding_id), ()):
                if positions[write] > positions[id(owner)] and route[:len(path)] == path:
                    stop, target = end, write
                    break
            for read in reads_by_binding.get(owner.binding_id, ()):
                if id(read) == target or stop is not None and positions[id(read)] > stop:
                    continue
                if positions[id(read)] <= positions[id(owner)]:
                    continue
                later = read_routes[id(read)]
                if route[:len(later)] == later or later[:len(route)] == route:
                    return False
            return True

        def owning_inputs(node):
            if isinstance(node, hir.Declare) and not node.view:
                return [node.expr]
            if isinstance(node, hir.FunctionCall):
                return [*node.pos_args, *node.kw_args.values()]
            if isinstance(node, hir.ObjectLiteral):
                return [field.value for field in node.fields]
            if isinstance(node, hir.ArrayLiteral):
                return node.items
            if isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign, hir.DictStore)):
                return [node.value] if node.value is not None else []
            return ()
        for block in blocks:
            local = {owner.binding_id for owner in parameter_owners} if block is body else set()
            for node in block.items:
                # Do not hoist a conditional consumption or a repeated loop
                # use into its parent lifetime. Nested blocks get their own
                # plan; owning arguments, fields and items share this rule.
                references = {}
                for read in hir.walk(node):
                    if isinstance(read, hir.ExpressedIdentifier):
                        references[read.binding_id] = references.get(read.binding_id, 0) + 1
                pending = [node]
                while pending:
                    part = pending.pop()
                    if isinstance(part, hir.Flow):
                        # The first if condition runs on every incoming path.
                        # Loop conditions repeat, and later arms are conditional.
                        if part.arms and isinstance(part.arms[0], hir.IfArm):
                            pending.append(part.arms[0].condition)
                        continue
                    if isinstance(part, (hir.Block, hir.FunctionLiteral, hir.ShortCircuit)):
                        continue
                    inputs = list(owning_inputs(part))
                    if part is node and resource(block.type) is not None and resource(part.type) is not None:
                        # A scoped expression's value is another owning input.
                        # The same last-use proof includes trailing statements
                        # and aliases, so it can consume only a branch local.
                        inputs.append(part)
                    for value in inputs:
                        while isinstance(value, (hir.ValueCast, hir.RepresentationCast, hir.Obligation)):
                            value = value.value if isinstance(value, hir.Obligation) else value.expr
                        owner = value
                        while isinstance(owner, (hir.MemberAccess, hir.Index)):
                            owner = owner.value if isinstance(owner, hir.MemberAccess) else owner.array
                        if (isinstance(owner, hir.ExpressedIdentifier) and resource(value.type) is not None
                                and owner.binding_id in local and owner.binding_id not in captured
                                and last_component(value, owner, block) and occurrences[id(owner)] == 1
                                and references.get(owner.binding_id) == 1 and not alive_after(owner.binding_id, id(owner))):
                            consumes.add(id(value))
                    pending.extend(hir.children(part))
                if not isinstance(node, hir.Declare):
                    continue
                source = node.expr
                if (isinstance(source, hir.ExpressedIdentifier)
                        and source.binding_id in local and source.binding_id not in captured
                        and last.get(source.binding_id) == id(source) and occurrences[id(source)] == 1
                        and not alive_after(source.binding_id, id(source))):
                    result.add(id(node))
                if (isinstance(source, hir.ExpressedIdentifier) and source.binding_id in lexical
                        and not {source.binding_id, node.binding_id} & (captured | written)):
                    views.add(id(node))
                if resource(source.type) is not None:
                    local.add(node.binding_id)
        return result, views, consumes

    def returnable_result(node):
        """Recognize a function result whose ownership can be made explicit."""
        if node.type == ty.BOTTOM_TYPE:
            return True
        if resource(node.type) is None:
            return False
        if isinstance(node, hir.Block):
            values = [item for item in node.items if item.type != ty.VOID_TYPE]
            return len(values) == 1 and returnable_result(values[0])
        if isinstance(node, hir.Flow):
            return (node.default is not None and returnable_result(node.default)
                    and all(isinstance(arm, hir.IfArm) and returnable_result(arm.body) for arm in node.arms))
        return True

    def return_result(node):
        if node.type == ty.BOTTOM_TYPE:
            return node
        if isinstance(node, hir.Block):
            index = next(i for i, item in enumerate(node.items) if item.type != ty.VOID_TYPE)
            if index == len(node.items) - 1:
                return replace(node, type=ty.BOTTOM_TYPE, items=[*node.items[:-1], return_result(node.items[-1])])
            # Preserve the value's original evaluation point, then execute
            # every trailing statement before transferring the saved owner.
            declaration, result = capture(node.items[index], node.loc)
            items = [*node.items[:index], declaration, *node.items[index + 1:], hir.Return(node.loc, ty.BOTTOM_TYPE, result)]
            return replace(node, type=ty.BOTTOM_TYPE, items=items)
        if isinstance(node, hir.Flow):
            return replace(node, type=ty.BOTTOM_TYPE,
                           arms=[replace(arm, type=ty.BOTTOM_TYPE, body=return_result(arm.body)) for arm in node.arms],
                           default=return_result(node.default))
        return hir.Return(node.loc, ty.BOTTOM_TYPE, node)

    def function(literal):
        nonlocal current_source
        if literal.proof or selected is not None and id(literal) not in selected:
            return literal
        previous_source = current_source
        current_source = literal.source or srcfile
        params = [*literal.pos_or_kw_args, *literal.kw_only_args]
        if literal.rest_args is not None:
            params.append(literal.rest_args)
        allowed = set()
        parameter_owners = []
        for param in params:
            if resource(param.type) is not None:
                if not param.place:
                    value = hir.ExpressedIdentifier(literal.loc, param.type, param.name, binding_id=param.binding_id)
                    parameter_owners.append(hir.Declare(literal.loc, ty.VOID_TYPE, 'let', param.name, param.type, value, binding_id=param.binding_id))
                allowed.add(param.binding_id)
        owning_result = resource(literal.rettype) is not None
        composed_parent = None
        if literal.lifecycle_composition and literal.lifecycle in ('copy', 'move'):
            assert isinstance(literal.body, hir.Block) and len(literal.body.items) == 2
            parent = literal.body.items[0]
            assert isinstance(parent, hir.Declare)
            composed_parent = parent.binding_id
        if literal.lifecycle is None and not mentions_resource(literal):
            current_source = previous_source
            return literal
        def deactivate(source, loc):
            flag = ownership_flags.get(source.binding_id)
            if flag is None:
                return []
            return [hir.Assign(loc, ty.VOID_TYPE, flag[1], '=', hir.Bool(loc, 'bool', False))]

        def statement(node, owners, loops, *, entry=False, fresh_result=False):
            live = allowed | {owner.binding_id for owner in owners}
            def control(child, *, consume=False, fresh_result=False):
                if consume:
                    if id(child) not in consumes:
                        return None
                    if isinstance(child, (hir.MemberAccess, hir.Index)):
                        projection = returning_projection(child, owners)
                        if projection is None:
                            return None
                        prefix = []
                        selected = freeze_route(child, child.loc, projection[0], prefix)
                        projection = returning_projection(selected, owners)
                        value, moved = transfer(selected, child.type)
                        saved, value = capture(value, child.loc)
                        flag = (component_flags.get(projection[0], {}).get(projection[1])
                                if all(isinstance(step, str) for step in projection[1]) else None)
                        if flag is not None:
                            # Consumed on this path only: the owner's cleanup
                            # consults the flag instead of a static route.
                            cleared = hir.Assign(child.loc, ty.VOID_TYPE, flag[1], '=', hir.Bool(child.loc, 'bool', False))
                            return hir.Block(child.loc, value.type, [*prefix, saved, cleared, value], False)
                        extractions.setdefault(projection[0], []).append((projection[1], moved))
                        # Keep the wrapper alive until its lexical cleanup. Only
                        # this component transfers; siblings still drop there.
                        return hir.Block(child.loc, value.type, [*prefix, saved, value], False)
                    source = next((owner for owner in owners if owner.binding_id == child.binding_id), None)
                    if source is None:
                        return None
                    value, moved = transfer(child, child.type)
                    if source.binding_id not in ownership_flags:
                        owners.remove(source)
                    if moved or source.binding_id in ownership_flags:
                        saved, value = capture(value, child.loc)
                        calls = cleanup([source], child.loc, {source.binding_id}) if moved else []
                        return hir.Block(child.loc, value.type, [saved, *calls, *deactivate(source, child.loc), value], False)
                    return value
                # Expression blocks have their own temporaries, but a return
                # from inside them leaves every surrounding owner too.
                if isinstance(child, hir.Block):
                    child = replace(child, scoped=True)
                return statement(child, list(owners), loops, fresh_result=fresh_result)
            if isinstance(node, hir.OrThrow):
                # Use the same checked control flow as the native checker.
                # Backend-created returns are too late for lifecycle/effects.
                binding = hir.Declare(node.loc, ty.VOID_TYPE, 'let', node.name,
                                      node.value.type, node.value, binding_id=node.binding_id)
                tested = hir.ExpressedIdentifier(node.loc, node.value.type, node.name, binding_id=node.binding_id)
                condition = hir.TypeTest(node.loc, 'bool', tested, node.exception_type, False)
                returned = hir.Return(node.loc, ty.BOTTOM_TYPE, node.propagated)
                arm = hir.IfArm(node.loc, ty.VOID_TYPE, condition, returned)
                value = hir.ExpressedIdentifier(node.loc, node.type, node.name, binding_id=node.binding_id)
                block = hir.Block(node.loc, node.type, [binding, hir.Flow(node.loc, ty.VOID_TYPE, [arm], None), value], True)
                return statement(block, list(owners), loops)
            if isinstance(node, hir.Block):
                active = list(owners) if node.scoped else owners
                start = 0 if entry else len(active)
                items = []
                for item in node.items:
                    items.append(statement(item, active, loops, fresh_result=fresh_result and resource(item.type) is not None))
                    if isinstance(item, hir.Declare) and item.binding_id in ownership_flags:
                        items.append(ownership_flags[item.binding_id][0])
                    if isinstance(item, hir.Declare):
                        items.extend(flag[0] for flag in component_flags.get(item.binding_id, {}).values())
                local = active[start:]
                if local and node.scoped:
                    result = None
                    if node.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
                        expressed = [i for i, item in enumerate(items) if item.type != ty.VOID_TYPE]
                        if len(expressed) != 1:
                            reject(node, 'an implicit result without a unique value')
                        index = expressed[0]
                        items[index], result = capture(items[index], node.loc)
                    items.extend(cleanup(local, node.loc))
                    if result is not None:
                        items.append(result)
                return replace(node, items=items)
            if isinstance(node, hir.Declare) and resource(node.annotation or node.expr.type) is not None:
                expected = ty.structural_base(node.annotation or node.expr.type)
                actual = ty.structural_base(node.expr.type)
                same_array = isinstance(expected, ty.ArrayType) and isinstance(actual, ty.ArrayType) and expected.element == actual.element
                same_union = isinstance(expected, ty.TypeOr) and (resource(actual) is None or any(
                    ty.structural_base(member) == actual for member in expected.items))
                # A checked top-level refinement changes facts, not ownership
                # layout (for example totaldict over an ordinary dict literal).
                same_storage = expected == actual
                if (node.binding_id is None
                        or node.annotation is not None and not same_storage and not same_array and not same_union):
                    reject(node, 'a non-fresh local owner')
                if id(node) in transfers and not node.view:
                    source = next((owner for owner in owners if owner.binding_id == node.expr.binding_id), None)
                    if source is not None:
                        value, moved = transfer(node.expr, node.annotation or node.expr.type)
                        if source.binding_id not in ownership_flags:
                            owners.remove(source)
                        node = replace(node, expr=value)
                        owners.append(node)
                        # The source's storage stays alive through the hook.
                        # A hook consumes its owner, not every nested field.
                        calls = cleanup([source], node.loc, {source.binding_id}) if moved else []
                        calls.extend(deactivate(source, node.loc))
                        return hir.Block(node.loc, node.type, [node, *calls], False) if calls else node
                if id(node) in views and isinstance(node.expr, hir.ExpressedIdentifier) and node.expr.binding_id in live:
                    # Both names only read. Keep one logical owner and require
                    # lowering to preserve this checked, nonowning lifetime.
                    allowed.add(node.binding_id)
                    return replace(node, view=True)
                if node.view:
                    reject(node, 'a resource view without a stable lifetime')
                node = replace(node, expr=fresh(node.expr, live, literal.lifecycle == 'drop', control=control))
                owners.append(node)
                return node
            if isinstance(node, hir.Assign) and (node.target.binding_id in live or resource(node.target.type) is not None):
                source = next((owner for owner in owners if owner.binding_id == node.target.binding_id), None)
                if source is None or node.op != '=':
                    reject(node, 'replacement without a local owning binding')
                # Evaluate the replacement before the old owner's drop can
                # change fields used by its initializer. The same binding
                # remains the owner and is cleaned up again at scope exit.
                declaration, value = capture(fresh(node.value, live, False, control=control), node.loc)
                flag = ownership_flags.get(source.binding_id)
                activate = [hir.Assign(node.loc, ty.VOID_TYPE, flag[1], '=', hir.Bool(node.loc, 'bool', True))] if flag is not None else []
                activate.extend(hir.Assign(node.loc, ty.VOID_TYPE, component[1], '=', hir.Bool(node.loc, 'bool', True))
                                for component in component_flags.get(source.binding_id, {}).values())
                released = cleanup([source], node.loc)
                extractions.pop(source.binding_id, None)
                return hir.Block(node.loc, node.type, [declaration, *released,
                                                       replace(node, value=value), *activate], False)
            if isinstance(node, hir.Return):
                consumed = None
                moved = False
                extracted = None
                prefix = []
                if node.item is not None and owning_result and resource(node.item.type) is not None:
                    # Returning leaves this path, so a named local owner is
                    # at its last use. Borrowed parameters are deliberately
                    # absent from owners: lending cannot transfer ownership.
                    if composed_parent is not None:
                        assert isinstance(node.item, hir.ObjectLiteral)
                        components = {composed_parent}
                        if literal.lifecycle == 'move':
                            # Only compiler-generated composition may adopt
                            # fields through its internal borrowed receiver.
                            components.add(params[0].binding_id)
                        returned = fresh(node.item, live, False, components, control)
                        consumed = composed_parent
                    elif isinstance(node.item, hir.ExpressedIdentifier) and any(owner.binding_id == node.item.binding_id for owner in owners):
                        returned, moved = transfer(node.item, literal.rettype)
                        consumed = node.item.binding_id
                    elif (projection := returning_projection(node.item, owners)) is not None:
                        selected = freeze_route(node.item, node.loc, projection[0], prefix)
                        projection = returning_projection(selected, owners)
                        returned, moved = transfer(selected, literal.rettype)
                        extracted = (*projection, moved)
                    else:
                        returned = fresh(node.item, live, False, control=control)
                else:
                    returned = expression(node.item, live, inherited=literal.lifecycle == 'drop', control=control) if node.item is not None else None
                if not owners:
                    return replace(node, item=returned)
                result = prefix
                if returned is not None and not isinstance(returned, hir.NoneValue):
                    declaration, returned = capture(returned, node.loc)
                    result.append(declaration)
                result.extend(cleanup([owner for owner in owners if moved or owner.binding_id != consumed], node.loc,
                                      {consumed} if moved else frozenset(), extracted=extracted))
                result.append(replace(node, item=returned))
                return hir.Block(node.loc, node.type, result, False)
            if isinstance(node, (hir.Break, hir.Continue)):
                if node.loop_levels >= len(loops):
                    reject(node, 'an unresolved loop cleanup boundary')
                released = owners[loops[-1 - node.loop_levels]:]
                return hir.Block(node.loc, node.type, [*cleanup(released, node.loc), node], False) if released else node
            if isinstance(node, hir.Flow):
                arms = []
                for arm in node.arms:
                    iterators = ([arm.condition] if isinstance(arm.condition, hir.IteratorExpression) else
                                 arm.condition.iterators if isinstance(arm.condition, hir.MultiIteratorExpression) else [])
                    borrowed = {it.target.binding_id for it in iterators} & iteration_loans
                    previous_allowed = set(allowed)
                    allowed.update(borrowed)
                    condition = expression(arm.condition, live | borrowed, inherited=literal.lifecycle == 'drop', control=control)
                    boundaries = [*loops, len(owners)] if isinstance(arm, hir.LoopArm) else loops
                    body = arm.body if isinstance(arm.body, hir.Block) else hir.Block(arm.body.loc, arm.body.type, [arm.body], True)
                    body = statement(body, list(owners), boundaries, fresh_result=fresh_result)
                    arms.append(replace(arm, condition=condition, body=body))
                    allowed.clear()
                    allowed.update(previous_allowed)
                default = node.default
                if default is not None:
                    if not isinstance(default, hir.Block):
                        default = hir.Block(default.loc, default.type, [default], True)
                    default = statement(default, list(owners), loops, fresh_result=fresh_result)
                return replace(node, arms=arms, default=default)
            if isinstance(node, hir.Declare) and isinstance(node.expr, hir.FunctionLiteral):
                return replace(node, expr=function(node.expr))
            if isinstance(node, (hir.MemberAssign, hir.IndexAssign)) and resource(node.target.type) is not None:
                # Capture selectors before the replacement, and the replacement
                # before drop. The route remains rooted in its actual owner;
                # neither an index expression nor the old hook runs twice.
                borrowed = expression(hir.Place(node.loc, node.target.type, node.target), live,
                                      inherited=literal.lifecycle == 'drop', control=control)
                selected = borrowed.target
                root_id = bindings.access_path(selected, dictionaries=True).binding_id
                prefix = []
                selected = freeze_route(selected, node.loc, root_id, prefix)
                check_selection(node.value, root_id)
                declaration, value = capture(fresh(node.value, live, False, control=control), node.loc)
                # The new value restores every component under this route.
                route = field_route(selected)
                activate = [] if route is None else [
                    hir.Assign(node.loc, ty.VOID_TYPE, flag[1], '=', hir.Bool(node.loc, 'bool', True))
                    for path, flag in component_flags.get(route[0], {}).items() if path[:len(route[1])] == route[1]]
                return hir.Block(node.loc, node.type, [*prefix, declaration,
                    *cleanup((), node.loc, selected=selected), replace(node, target=selected, value=value), *activate], False)
            if isinstance(node, hir.MemberAssign):
                return replace(node, target=expression(node.target, live, inherited=literal.lifecycle == 'drop', control=control),
                               value=expression(node.value, live, inherited=literal.lifecycle == 'drop', control=control))
            if (owning_result or fresh_result) and resource(node.type) is not None:
                return fresh(node, live, False, control=control)
            return expression(node, live, inherited=literal.lifecycle == 'drop', control=control)

        # A function body's unscoped block is nevertheless its lexical owner
        # scope, as in normal backend cleanup.
        body = literal.body
        if owning_result and returnable_result(body):
            body = return_result(body)
        if not isinstance(body, hir.Block):
            body = hir.Block(body.loc, body.type, [body], True)
        elif not body.scoped:
            body = replace(body, scoped=True)
        transfers, views, consumes = local_transfers(body, parameter_owners, allowed)
        def component(node):
            # A hook-free route to a component without a custom move: the
            # remaining owner can drop around it, guarded by one flag.
            shape = ty.structural_base(node.type)
            if not isinstance(shape, ty.ObjectType) or any(method.lifecycle == 'move' for method in shape.methods):
                return False
            while isinstance(node, hir.MemberAccess):
                owner_shape = ty.structural_base(node.value.type)
                if not isinstance(owner_shape, ty.ObjectType) or any(method.lifecycle is not None for method in owner_shape.methods):
                    return False
                node = node.value
            return True
        conditional, declarations_by_read = conditional_consumptions(body, parameter_owners, resource, component)
        for read, (owner, path) in conditional.items():
            if path:
                if read not in consumes:
                    consumes.add(read)
                    flags = component_flags.setdefault(owner, {})
                    if path not in flags:
                        flags[path] = capture(hir.Bool(literal.loc, 'bool', True), literal.loc)
                continue
            declaration = declarations_by_read.get(read)
            if read in consumes or declaration in transfers:
                continue
            if declaration is not None:
                transfers.add(declaration)
            else:
                consumes.add(read)
            if owner not in ownership_flags:
                ownership_flags[owner] = capture(hir.Bool(literal.loc, 'bool', True), literal.loc)
        prepared_body = statement(body, list(parameter_owners), [], entry=True)
        prefix = [ownership_flags[owner.binding_id][0] for owner in parameter_owners if owner.binding_id in ownership_flags]
        prefix.extend(flag[0] for owner in parameter_owners for flag in component_flags.get(owner.binding_id, {}).values())
        if prefix:
            prepared_body = replace(prepared_body, items=[*prefix, *prepared_body.items])
        prepared = replace(literal, body=prepared_body)
        def parameter(param):
            return replace(param, value=argument(param.value, allowed, False)) if isinstance(param, hir.BoundParam) else param
        result = replace(prepared, pos_or_kw_args=[parameter(p) for p in literal.pos_or_kw_args],
                         kw_only_args=[parameter(p) for p in literal.kw_only_args],
                         rest_args=parameter(literal.rest_args))
        current_source = previous_source
        return result

    items = []
    for item in root.items:
        if isinstance(item, hir.Declare) and isinstance(item.expr, hir.FunctionLiteral):
            items.append(replace(item, expr=function(item.expr)))
        else:
            if not isinstance(item, (hir.TypeValue, hir.ScopeMetatag)):
                expression(item, set())
            items.append(item)
    prepared = replace(root, items=[*items, *generated])
    if isinstance(prepared, hir.Program):
        prepared = replace(prepared, item_sources=(*root.item_sources, *(node.expr.source or srcfile for node in generated)))
    # Refresh checked definitions: fact/effect resolution must see cleanup
    # inside callees as well as in the current function.
    for node in hir.walk(prepared):
        if isinstance(node, hir.Declare) and node.binding_id in registry.by_id:
            binding = registry.by_id[node.binding_id]
            binding.declaration = node
            if isinstance(node.expr, hir.FunctionLiteral):
                binding.function = node.expr
    if validate:
        from .analyze import bounds
        bounds.validate_bounds(prepared, registry, srcfile, target=root.target)
        public_effects.validate(prepared, registry, srcfile)
    return replace(prepared, ownership_prepared=selected is None) if isinstance(prepared, hir.Program) else prepared
