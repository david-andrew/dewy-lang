"""Materialize ownership operations before runtime lowering.

The first supported owners are fresh local nominal records with word fields
and a drop hook. Copies, moves, aggregate fields and escaping owners remain
explicitly unsupported. Keeping drop calls in checked HIR makes their effects
visible and lets ordinary lowering implement the internal place call ABI.
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

    for declaration in declarations.values():
        literal = declaration.expr
        current_source = literal.source or srcfile
        receiver = ty.unfold(ty.strip_refinement(literal.pos_or_kw_args[0].type))
        if literal.lifecycle != 'drop' or not isinstance(receiver, ty.ObjectType):
            reject(declaration, 'copy/move hooks')
        if not all(public_effects.scalar(field.type) for field in receiver.fields):
            reject(declaration, 'owners with aggregate fields')

    current_source = srcfile

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

    def cleanup(owners, loc):
        result = []
        for owner in reversed(owners):
            owner_type = ty.unfold(ty.strip_refinement(owner.expr.type))
            hook = next(method for method in owner_type.methods if method.lifecycle == 'drop')
            declaration = declarations.get(hook.binding_id)
            if declaration is None:
                reject(owner, 'an unavailable drop operation')
            function = hir.ExpressedIdentifier(loc, declaration.expr.type, declaration.name, binding_id=declaration.binding_id)
            value = hir.ExpressedIdentifier(loc, owner_type, owner.name, binding_id=owner.binding_id)
            result.append(hir.FunctionCall(loc, ty.VOID_TYPE, function, [hir.Place(loc, owner_type, value)], {}))
        return result

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
            if (not isinstance(node.value, hir.ExpressedIdentifier) or node.value.binding_id not in allowed
                    or not public_effects.scalar(node.type)):
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
                path = path.value if isinstance(path, hir.MemberAccess) else path.array
            if resource(path.type) is not None:
                reject(node, 'an exposed resource owner')
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
        for index, param in enumerate(params):
            if resource(param.type) is not None:
                if not (literal.lifecycle == 'drop' and index == 0 and param.place):
                    reject(literal, 'owning parameters')
                allowed.add(param.binding_id)
        if resource(literal.rettype) is not None:
            reject(literal, 'owning returns')
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
                    if node.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
                        reject(node, 'an implicit value return with local owners')
                    items.extend(cleanup(local, node.loc))
                return replace(node, items=items)
            if isinstance(node, hir.Declare) and resource(node.expr.type) is not None:
                owner_type = ty.unfold(ty.strip_refinement(node.expr.type))
                if (not isinstance(node.expr, hir.ObjectLiteral) or not isinstance(owner_type, ty.ObjectType)
                        or not any(method.lifecycle == 'drop' for method in owner_type.methods)
                        or node.binding_id is None or node.view
                        or node.annotation is not None and node.annotation != node.expr.type):
                    reject(node, 'a non-fresh local owner')
                hook = next(method for method in owner_type.methods if method.lifecycle == 'drop')
                operation = declarations.get(hook.binding_id)
                if operation is None or ty.unfold(ty.strip_refinement(operation.expr.pos_or_kw_args[0].type)) != owner_type:
                    reject(node, 'an adapted drop receiver without a checked composition')
                fields = [replace(field, value=expression(field.value, live, inherited=literal.lifecycle == 'drop')) for field in node.expr.fields]
                node = replace(node, expr=replace(node.expr, fields=fields))
                owners.append(node)
                return node
            if isinstance(node, hir.Return):
                returned = expression(node.item, live, inherited=literal.lifecycle == 'drop') if node.item is not None else None
                if not owners:
                    return replace(node, item=returned)
                result = []
                if returned is not None:
                    if not public_effects.scalar(returned.type):
                        reject(node, 'a non-word return with local owners')
                    name = f'__dewy_drop_result_{registry.next_id}'
                    binding = registry.allocate(object(), name, 'value', node.loc)
                    binding.type = returned.type
                    declaration = hir.Declare(node.loc, ty.VOID_TYPE, 'let', name, returned.type, returned, binding_id=binding.id)
                    binding.declaration = declaration
                    result.append(declaration)
                    returned = hir.ExpressedIdentifier(node.loc, returned.type, name, binding_id=binding.id)
                result.extend(cleanup(owners, node.loc))
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
