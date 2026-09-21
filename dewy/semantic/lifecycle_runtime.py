"""Materialize ownership operations before runtime lowering.

Fresh records and arrays own their nested resources; factories, ordinary
by-value parameters and results transfer fresh owners. Checked @ parameters
borrow. Same-scope bindings can move at last use, and custom copy/move hooks
remain checked calls. Drop precedes field/element storage cleanup.

Conditional consumption of outer owners, field transfers, inferred copies
and resource-container mutation still need the general lifetime plan.
"""
from dataclasses import replace

from . import hir, ty
from ..parser import t0
from .errors import not_implemented
from .analyze import public_effects


def prepare(root: hir.Block, srcfile, *, selected: set[int] | None = None, validate: bool = True):
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

    array_drops = {}
    generated = []

    def cleanup(owners, loc, fields_only=frozenset()):
        result = []
        def drop(value, type_, ancestors, run_hook=True, into=result):
            if resource(type_) is None:
                return
            shape = ty.unfold(ty.strip_refinement(type_))
            if id(shape) in ancestors:
                reject(value, 'recursive resource storage')
            if isinstance(shape, ty.ArrayType):
                # One checked helper per array shape: its borrowed receiver
                # has a stable identity even for an outer array's element.
                # Reuse also avoids duplicating nested cleanup loops at exits.
                operation = array_drops.get(shape)
                if operation is None:
                    name = f'__dewy_drop_array_{registry.next_id}'
                    binding = registry.allocate(object(), name, 'value', loc)
                    parameter = registry.allocate(object(), '__items', 'param', loc)
                    parameter.type = shape
                    signature = ty.FunctionType([ty.PosOrKwArg('__items', shape, place=True)], [], None, ty.VOID_TYPE)
                    binding.type = signature
                    operation = hir.ExpressedIdentifier(loc, signature, name, binding_id=binding.id)
                    receiver = hir.ExpressedIdentifier(loc, shape, parameter.name, binding_id=parameter.id)
                    declaration, cursor = capture(hir.ArrayLength(loc, 'int64', receiver), loc)
                    zero = hir.Integer(loc, 'int64', t0.base10, 0)
                    one = hir.Integer(loc, 'int64', t0.base10, 1)
                    comparison = hir.ExpressedIdentifier(loc, ty.FunctionType(
                        [ty.PosOrKwArg(None, 'int64'), ty.PosOrKwArg(None, 'int64')], [], None, 'bool'), '__gt__')
                    condition = hir.FunctionCall(loc, 'bool', comparison, [cursor, zero], {})
                    element_calls = []
                    drop(hir.Index(loc, shape.element, receiver, cursor, None), shape.element, ancestors | {id(shape)}, into=element_calls)
                    body = hir.Block(loc, ty.VOID_TYPE, [hir.Assign(loc, ty.VOID_TYPE, cursor, '-=', one), *element_calls], True)
                    loop = hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(loc, ty.VOID_TYPE, condition, body)])
                    literal = hir.FunctionLiteral(loc, signature, [hir.Param(parameter.name, shape, binding_id=parameter.id, place=True)], [], None,
                                                  ty.VOID_TYPE, hir.Block(loc, ty.VOID_TYPE, [declaration, loop], True), source=current_source)
                    declared = hir.Declare(loc, ty.VOID_TYPE, 'const', name, signature, literal, binding_id=binding.id)
                    binding.function = literal
                    binding.declaration = declared
                    generated.append(declared)
                    array_drops[shape] = operation
                into.append(hir.FunctionCall(loc, ty.VOID_TYPE, replace(operation, loc=loc), [hir.Place(loc, shape, value)], {}))
                return
            if not isinstance(shape, ty.ObjectType):
                reject(value, 'resource union storage')
            hook = next((method for method in shape.methods if method.lifecycle == 'drop'), None)
            if hook is not None and run_hook:
                declaration = declarations.get(hook.binding_id)
                if declaration is None:
                    reject(value, 'an unavailable drop operation')
                function = hir.ExpressedIdentifier(loc, declaration.expr.type, declaration.name, binding_id=declaration.binding_id)
                into.append(hir.FunctionCall(loc, ty.VOID_TYPE, function, [hir.Place(loc, shape, value)], {}))
            # Parent body first; then fields in reverse declaration order.
            # Ordinary lowering releases the complete backing storage afterward.
            for field in reversed(shape.fields):
                if resource(field.type) is not None:
                    drop(hir.MemberAccess(loc, field.type, value, field.name), field.type, ancestors | {id(shape)}, into=into)
        for owner in reversed(owners):
            owner_type = owner.annotation or owner.expr.type
            value = hir.ExpressedIdentifier(loc, owner_type, owner.name, binding_id=owner.binding_id)
            drop(value, owner_type, set(), owner.binding_id not in fields_only)
        return result

    def transfer(value, expected):
        shape = ty.unfold(ty.strip_refinement(value.type))
        if not isinstance(shape, ty.ObjectType):
            return value, False
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

    def fresh(node, allowed, inherited, components=frozenset(), control=None):
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
                if isinstance(receiver, (hir.FunctionCall, hir.ObjectLiteral)):
                    # A temporary receiver owns its resource until the copy
                    # finishes. Snapshot the result before dropping that
                    # receiver; neither evaluation nor cleanup is duplicated.
                    owner, borrowed = capture(fresh(receiver, allowed, inherited, control=control), node.loc)
                    copied = replace(node, pos_args=[replace(node.pos_args[0], target=borrowed)])
                    result, value = capture(copied, node.loc)
                    return hir.Block(node.loc, node.type, [owner, result, *cleanup([owner], node.loc), value], False)
                while isinstance(receiver, hir.MemberAccess):
                    receiver = receiver.value
                if not isinstance(receiver, hir.ExpressedIdentifier) or receiver.binding_id not in allowed:
                    reject(node, 'an unavailable copy receiver')
                return node
            # A function result is an owned value, including through a
            # callback. Every checked body owes the same return contract;
            # resource arguments still require their own ownership proof.
            return replace(node, func=expression(node.func, allowed, inherited=inherited, control=control),
                           pos_args=[argument(arg, allowed, inherited, control) for arg in node.pos_args],
                           kw_args={name: argument(arg, allowed, inherited, control) for name, arg in node.kw_args.items()})
        shape = ty.unfold(ty.strip_refinement(node.type))
        if isinstance(node, hir.ArrayLiteral) and isinstance(shape, ty.ArrayType):
            return replace(node, items=[fresh(item, allowed, inherited, components, control) for item in node.items])
        if not isinstance(node, hir.ObjectLiteral) or not isinstance(shape, ty.ObjectType):
            reject(node, 'a non-fresh resource field or resource container')
        hook = next((method for method in shape.methods if method.lifecycle == 'drop'), None)
        if hook is not None:
            operation = declarations.get(hook.binding_id)
            if operation is None or ty.unfold(ty.strip_refinement(operation.expr.pos_or_kw_args[0].type)) != shape:
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
        # Hosted HIR is immutable-by-replacement: retain rewritten control
        # flow in a selector, not just its successful validation.
        if isinstance(node, hir.MemberAccess):
            return replace(node, value=route_indices(node.value, allowed, inherited, control))
        if isinstance(node, hir.Index):
            return replace(node, array=route_indices(node.array, allowed, inherited, control),
                           index=expression(node.index, allowed, inherited=inherited, control=control))
        return node

    def expression(node, allowed, *, inherited=False, control=None):
        if control is not None and isinstance(node, (hir.Block, hir.Flow, hir.Return, hir.Break, hir.Continue, hir.OrThrow)):
            return control(node)
        if isinstance(node, hir.FunctionLiteral):
            return function(node)
        if (isinstance(node, hir.TypeValue)
                or isinstance(node, hir.FunctionCall) and node.proof
                or isinstance(node, hir.Assert) and not node.runtime and not node.expect):
            return node
        if (isinstance(node, hir.MemberAccess) and resource(node.value.type) is not None
                or isinstance(node, hir.ArrayLength) and resource(node.array.type) is not None):
            selected = route_indices(node.value if isinstance(node, hir.MemberAccess) else node.array, allowed, inherited, control)
            owner = selected
            while isinstance(owner, (hir.MemberAccess, hir.Index)):
                if isinstance(owner, hir.Index):
                    owner = owner.array
                else:
                    owner = owner.value
            if (not isinstance(owner, hir.ExpressedIdentifier) or owner.binding_id not in allowed
                    or resource(node.type) is not None):
                reject(node, 'an escaping or projected resource owner')
            return replace(node, **({'value': selected} if isinstance(node, hir.MemberAccess) else {'array': selected}))
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
            while isinstance(path, (hir.MemberAccess, hir.Index)):
                path = path.value if isinstance(path, hir.MemberAccess) else path.array
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

    def local_transfers(body):
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
            if isinstance(node, hir.Transmute):
                written_root(node.expr)
            if isinstance(node, hir.ExpressedIdentifier):
                last[node.binding_id] = id(node)
                occurrences[id(node)] = occurrences.get(id(node), 0) + 1
            if isinstance(node, hir.Block):
                blocks.append(node)
            pending.extend(reversed(tuple(hir.children(node))))
        result, views = set(), set()
        for block in blocks:
            local = set()
            for node in block.items:
                if not isinstance(node, hir.Declare):
                    continue
                source = node.expr
                if (isinstance(source, hir.ExpressedIdentifier)
                        and source.binding_id in local and source.binding_id not in captured
                        and last.get(source.binding_id) == id(source) and occurrences[id(source)] == 1):
                    result.add(id(node))
                if (isinstance(source, hir.ExpressedIdentifier) and source.binding_id in local
                        and not {source.binding_id, node.binding_id} & (captured | written)):
                    views.add(id(node))
                if resource(source.type) is not None:
                    local.add(node.binding_id)
        return result, views

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
        def statement(node, owners, loops, *, entry=False):
            live = allowed | {owner.binding_id for owner in owners}
            def control(child):
                # Expression blocks have their own temporaries, but a return
                # from inside them leaves every surrounding owner too.
                if isinstance(child, hir.Block):
                    child = replace(child, scoped=True)
                return statement(child, list(owners), loops)
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
                expected = ty.unfold(ty.strip_refinement(node.annotation or node.expr.type))
                actual = ty.unfold(ty.strip_refinement(node.expr.type))
                same_array = isinstance(expected, ty.ArrayType) and isinstance(actual, ty.ArrayType) and expected.element == actual.element
                if (node.binding_id is None
                        or node.annotation is not None and node.annotation != node.expr.type and not same_array):
                    reject(node, 'a non-fresh local owner')
                if id(node) in transfers:
                    source = next((owner for owner in owners if owner.binding_id == node.expr.binding_id), None)
                    if source is not None:
                        value, moved = transfer(node.expr, node.annotation or node.expr.type)
                        owners.remove(source)
                        node = replace(node, expr=value)
                        owners.append(node)
                        # The source's storage stays alive through the hook.
                        # A hook consumes its owner, not every nested field.
                        calls = cleanup([source], node.loc, {source.binding_id}) if moved else []
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
            if isinstance(node, hir.Return):
                consumed = None
                moved = False
                if node.item is not None and owning_result and resource(node.item.type) is not None:
                    # Returning leaves this path, so a named local owner is
                    # at its last use. Borrowed parameters are deliberately
                    # absent from owners: lending cannot transfer ownership.
                    if composed_parent is not None:
                        assert isinstance(node.item, hir.ObjectLiteral)
                        returned = fresh(node.item, live, False, {composed_parent}, control)
                        consumed = composed_parent
                    elif isinstance(node.item, hir.ExpressedIdentifier) and any(owner.binding_id == node.item.binding_id for owner in owners):
                        returned, moved = transfer(node.item, literal.rettype)
                        consumed = node.item.binding_id
                    else:
                        returned = fresh(node.item, live, False, control=control)
                else:
                    returned = expression(node.item, live, inherited=literal.lifecycle == 'drop', control=control) if node.item is not None else None
                if not owners:
                    return replace(node, item=returned)
                result = []
                if returned is not None and not isinstance(returned, hir.NoneValue):
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
                    condition = expression(arm.condition, live, inherited=literal.lifecycle == 'drop', control=control)
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
                return replace(node, target=expression(node.target, live, inherited=literal.lifecycle == 'drop', control=control),
                               value=expression(node.value, live, inherited=literal.lifecycle == 'drop', control=control))
            if owning_result and resource(node.type) is not None:
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
        transfers, views = local_transfers(body)
        prepared = replace(literal, body=statement(body, parameter_owners, [], entry=True))
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
