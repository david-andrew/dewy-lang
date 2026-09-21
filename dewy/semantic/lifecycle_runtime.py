"""Materialize ownership operations before runtime lowering.

Supported owners are fresh records, including nested record resources and
factory results transferred into their caller's ownership.
Explicit copy hooks may construct fresh results; drop runs before field
cleanup. Checked place parameters borrow without acquiring ownership.
Explicit returns transfer locals and invoke custom move hooks when present.
General local transfers, implicit copies, resource containers and owning parameters
remain unsupported. Checked HIR calls expose effects and use the ordinary
internal place call ABI.
"""
from dataclasses import replace

from . import hir, ty
from .errors import not_implemented
from .analyze import public_effects


def prepare(root: hir.Block, srcfile):
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
            type_ = ty.unfold(ty.strip_refinement(pending.pop()))
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
        receiver = ty.unfold(ty.strip_refinement(literal.pos_or_kw_args[0].type))
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

    def cleanup(owners, loc, fields_only=frozenset()):
        result = []
        def drop(value, type_, ancestors, run_hook=True):
            if resource(type_) is None:
                return
            shape = ty.unfold(ty.strip_refinement(type_))
            if not isinstance(shape, ty.ObjectType) or id(shape) in ancestors:
                reject(value, 'resource containers or recursive resource storage')
            hook = next((method for method in shape.methods if method.lifecycle == 'drop'), None)
            if hook is not None and run_hook:
                declaration = declarations.get(hook.binding_id)
                if declaration is None:
                    reject(value, 'an unavailable drop operation')
                function = hir.ExpressedIdentifier(loc, declaration.expr.type, declaration.name, binding_id=declaration.binding_id)
                result.append(hir.FunctionCall(loc, ty.VOID_TYPE, function, [hir.Place(loc, shape, value)], {}))
            # Parent body first; then fields in reverse declaration order.
            # Ordinary lowering releases the complete backing storage afterward.
            for field in reversed(shape.fields):
                if resource(field.type) is not None:
                    drop(hir.MemberAccess(loc, field.type, value, field.name), field.type, ancestors | {id(shape)})
        for owner in reversed(owners):
            value = hir.ExpressedIdentifier(loc, owner.expr.type, owner.name, binding_id=owner.binding_id)
            drop(value, owner.expr.type, set(), owner.binding_id not in fields_only)
        return result

    def transfer(value, expected):
        shape = ty.unfold(ty.strip_refinement(value.type))
        assert isinstance(shape, ty.ObjectType)
        hook = next((method for method in shape.methods if method.lifecycle == 'move'), None)
        if hook is None:
            return value, False
        operation = declarations.get(hook.binding_id)
        if operation is None:
            reject(value, 'an unavailable move operation')
        result_type = operation.expr.rettype
        if ty.unfold(ty.strip_refinement(result_type)) != shape:
            reject(value, 'an adapted move receiver without a checked composition')
        function = hir.ExpressedIdentifier(value.loc, operation.expr.type, operation.name, binding_id=operation.binding_id)
        result = hir.FunctionCall(value.loc, result_type, function, [hir.Place(value.loc, shape, value)], {})
        if isinstance(expected, ty.RefinedType):
            # The old value's facts are not facts about a hook's new result.
            result = hir.Obligation(value.loc, result_type, result, expected, 'the return contract after moving')
        return result, True

    def fresh(node, allowed, inherited, components=frozenset()):
        if isinstance(node, hir.MemberAccess):
            owner = node.value
            while isinstance(owner, hir.MemberAccess):
                owner = owner.value
            if isinstance(owner, hir.ExpressedIdentifier) and owner.binding_id in components:
                # The checked inheritance wrapper transfers every parent
                # field into its complete child, consuming that intermediate.
                return node
        # An explicit custom copy creates an independent owner. Its checked
        # call already carries the hook's effects and result contract.
        if isinstance(node, hir.FunctionCall):
            operation = declarations.get(node.func.binding_id) if isinstance(node.func, hir.ExpressedIdentifier) else None
            if operation is not None and operation.expr.lifecycle == 'copy':
                if len(node.pos_args) != 1 or node.kw_args or not isinstance(node.pos_args[0], hir.Place):
                    reject(node, 'an invalid copy receiver')
                receiver = node.pos_args[0].target
                while isinstance(receiver, hir.MemberAccess):
                    receiver = receiver.value
                if not isinstance(receiver, hir.ExpressedIdentifier) or receiver.binding_id not in allowed:
                    reject(node, 'an unavailable copy receiver')
                return node
            # A function result is an owned value, including through a
            # callback. Every checked body owes the same return contract;
            # resource arguments still require their own ownership proof.
            return replace(node, func=expression(node.func, allowed, inherited=inherited),
                           pos_args=[expression(arg, allowed, inherited=inherited) for arg in node.pos_args],
                           kw_args={name: expression(arg, allowed, inherited=inherited) for name, arg in node.kw_args.items()})
        shape = ty.unfold(ty.strip_refinement(node.type))
        if not isinstance(node, hir.ObjectLiteral) or not isinstance(shape, ty.ObjectType):
            reject(node, 'a non-fresh resource field or resource container')
        hook = next((method for method in shape.methods if method.lifecycle == 'drop'), None)
        if hook is not None:
            operation = declarations.get(hook.binding_id)
            if operation is None or ty.unfold(ty.strip_refinement(operation.expr.pos_or_kw_args[0].type)) != shape:
                reject(node, 'an adapted drop receiver without a checked composition')
        return replace(node, fields=[replace(field, value=fresh(field.value, allowed, inherited, components)
                                            if resource(field.value.type) is not None else expression(field.value, allowed, inherited=inherited))
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

    def expression(node, allowed, *, inherited=False):
        if isinstance(node, hir.FunctionLiteral):
            return function(node)
        if (isinstance(node, hir.TypeValue)
                or isinstance(node, hir.FunctionCall) and node.proof
                or isinstance(node, hir.Assert) and not node.runtime and not node.expect):
            return node
        if isinstance(node, hir.MemberAccess) and resource(node.value.type) is not None:
            owner = node.value
            while isinstance(owner, hir.MemberAccess):
                owner = owner.value
            if (not isinstance(owner, hir.ExpressedIdentifier) or owner.binding_id not in allowed
                    or resource(node.type) is not None):
                reject(node, 'an escaping or projected resource owner')
            return node
        if isinstance(node, hir.FunctionCall) and inherited and isinstance(node.func, hir.ExpressedIdentifier) and node.func.binding_id in declarations:
            # The checker generated this parent-portion drop invocation.
            if len(node.pos_args) != 1 or not isinstance(node.pos_args[0], hir.Place):
                reject(node, 'an invalid inherited drop receiver')
            value = node.pos_args[0].target
            if not isinstance(value, hir.ExpressedIdentifier) or value.binding_id not in allowed:
                reject(node, 'an escaping inherited drop receiver')
            return node
        if isinstance(node, hir.Place):
            path = node.target
            while isinstance(path, (hir.MemberAccess, hir.Index)):
                if isinstance(path, hir.Index):
                    expression(path.index, allowed, inherited=inherited)
                path = path.value if isinstance(path, hir.MemberAccess) else path.array
            if resource(path.type) is not None:
                # A checked place call borrows the existing owner. Its
                # lifetime and overlapping routes are checked by the normal
                # place rules; the callee must not acquire another owner.
                if not isinstance(path, hir.ExpressedIdentifier) or path.binding_id not in allowed:
                    reject(node, 'an unavailable resource borrow')
                return node
        if resource(node.type) is not None:
            reject(node, 'a resource copy, move, temporary, or escape')
        return replace(node, **{name: mapped(getattr(node, name), lambda child: expression(child, allowed, inherited=inherited))
                                for name in hir.child_fields(type(node))})

    def function(literal):
        nonlocal current_source
        if literal.proof:
            return literal
        previous_source = current_source
        current_source = literal.source or srcfile
        params = [*literal.pos_or_kw_args, *literal.kw_only_args]
        if literal.rest_args is not None:
            params.append(literal.rest_args)
        allowed = set()
        for param in params:
            if resource(param.type) is not None:
                if not param.place:
                    reject(literal, 'owning parameters')
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
        def statement(node, owners, loops):
            live = allowed | {owner.binding_id for owner in owners}
            if isinstance(node, hir.Block):
                active = list(owners) if node.scoped else owners
                start = len(active)
                items = []
                for item in node.items:
                    items.append(statement(item, active, loops))
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
            if isinstance(node, hir.Declare) and resource(node.expr.type) is not None:
                if (node.binding_id is None or node.view
                        or node.annotation is not None and node.annotation != node.expr.type):
                    reject(node, 'a non-fresh local owner')
                node = replace(node, expr=fresh(node.expr, live, literal.lifecycle == 'drop'))
                owners.append(node)
                return node
            if isinstance(node, hir.Return):
                consumed = None
                moved = False
                if node.item is not None and owning_result and resource(node.item.type) is not None:
                    # Returning leaves this path, so a named local owner is
                    # at its last use. Borrowed parameters are deliberately
                    # absent from owners: lending cannot transfer ownership.
                    if composed_parent is not None:
                        assert isinstance(node.item, hir.ObjectLiteral)
                        returned = fresh(node.item, live, False, {composed_parent})
                        consumed = composed_parent
                    elif isinstance(node.item, hir.ExpressedIdentifier) and any(owner.binding_id == node.item.binding_id for owner in owners):
                        returned, moved = transfer(node.item, literal.rettype)
                        consumed = node.item.binding_id
                    else:
                        returned = fresh(node.item, live, False)
                else:
                    returned = expression(node.item, live, inherited=literal.lifecycle == 'drop') if node.item is not None else None
                if not owners:
                    return replace(node, item=returned)
                result = []
                if returned is not None:
                    declaration, returned = capture(returned, node.loc)
                    result.append(declaration)
                result.extend(cleanup([owner for owner in owners if moved or owner.binding_id != consumed], node.loc,
                                      {consumed} if moved else frozenset()))
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
                    condition = expression(arm.condition, live, inherited=literal.lifecycle == 'drop')
                    boundaries = [*loops, len(owners)] if isinstance(arm, hir.LoopArm) else loops
                    body = arm.body if isinstance(arm.body, hir.Block) else hir.Block(arm.body.loc, arm.body.type, [arm.body], True)
                    body = statement(body, list(owners), boundaries)
                    arms.append(replace(arm, condition=condition, body=body))
                default = node.default
                if default is not None:
                    if not isinstance(default, hir.Block):
                        default = hir.Block(default.loc, default.type, [default], True)
                    default = statement(default, list(owners), loops)
                return replace(node, arms=arms, default=default)
            if isinstance(node, hir.Declare) and isinstance(node.expr, hir.FunctionLiteral):
                return replace(node, expr=function(node.expr))
            if isinstance(node, hir.MemberAssign):
                return replace(node, target=expression(node.target, live, inherited=literal.lifecycle == 'drop'),
                               value=expression(node.value, live, inherited=literal.lifecycle == 'drop'))
            if owning_result and resource(node.type) is not None:
                return fresh(node, live, False)
            return expression(node, live, inherited=literal.lifecycle == 'drop')

        # A function body's unscoped block is nevertheless its lexical owner
        # scope, as in normal backend cleanup.
        body = literal.body
        if not isinstance(body, hir.Block):
            body = hir.Block(body.loc, body.type, [body], True)
        elif not body.scoped:
            body = replace(body, scoped=True)
        prepared = replace(literal, body=statement(body, [], []))
        def parameter(param):
            return replace(param, value=expression(param.value, allowed)) if isinstance(param, hir.BoundParam) else param
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
    prepared = replace(root, items=items)
    # Refresh checked definitions: fact/effect resolution must see cleanup
    # inside callees as well as in the current function.
    for node in hir.walk(prepared):
        if isinstance(node, hir.Declare) and node.binding_id in registry.by_id:
            binding = registry.by_id[node.binding_id]
            binding.declaration = node
            if isinstance(node.expr, hir.FunctionLiteral):
                binding.function = node.expr
    from .analyze import bounds
    bounds.validate_bounds(prepared, registry, srcfile, target=root.target)
    public_effects.validate(prepared, registry, srcfile)
    return prepared
