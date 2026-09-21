"""Conservative public-effect checking, starting with explicit empty rows.

This is not the aggregate-access analysis used for borrow selection. A local
read/write is private, whereas a place or captured mutable value belongs to
someone else. Unsupported storage operations remain unknown until their
allocation/escape behavior has a checked model; unknown never means pure.
"""
from collections import deque

from .. import bindings, effect_rows as rows, hir, ty
from ..errors import user_error
from ...reporting import Pointer
from .effects import _EffectAnalyzer, _literal_params, _unwrap

SCALAR_OPERATIONS = frozenset({
    '__add__', '__sub__', '__mul__', '__div__', '__floordiv__', '__mod__',
    '__unary_sub__', '__not__', '__eq__', '__ne__', '__lt__', '__le__',
    '__gt__', '__ge__', '__and__', '__or__', '__xor__', '__nand__', '__nor__',
    '__xnor__', '__lshift__', '__rshift__',
})


def scalar(type_):
    type_ = ty.strip_refinement(type_)
    return isinstance(type_, ty.IntegerLiteralType) and -(1 << 63) <= type_.value < (1 << 64) or isinstance(type_, str) and type_ in {
        'void', 'never', 'none', 'bool', 'true', 'false',
        'int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64',
        'float32', 'float64',
    }


def word_iterator(node):
    """The counter/flags fit frame words; no runtime-sized storage is needed.

    Bounds validation has already certified `guarded` on every advancing
    edge. Finite ranges carry their exact extent directly in checked HIR.
    """
    if not isinstance(node.iterable, hir.Range) or ty.strip_refinement(node.target.type) not in ('int', 'uint', 'int64', 'uint64'):
        return False
    return (node.count is None and node.guarded) or node.count is not None and all(
        value is None or ty.integer_literal_fits(value, 'int64')
        for value in (node.first, node.step, node.last, node.count))


def validate(root, registry, srcfile):
    # Do not add a second whole-program fixed point to unannotated programs.
    constrained = [node for node in hir.walk(root) if isinstance(node, hir.FunctionLiteral)
                   and isinstance(node.type, ty.FunctionType) and node.type.effects is not None]
    if not constrained:
        return
    analysis = _EffectAnalyzer(root)
    storage_effects = analysis.solve()
    local = {}
    calls = {}
    dependents = {}
    for literal in analysis.literals:
        key = id(literal)
        params = _literal_params(literal)
        # A lifecycle receiver is logically the operated-on value. Its
        # internal place ABI does not introduce a public external resource:
        # copy reads it; move/drop consume it. Storage alias analysis still
        # sees the place and checks all actual reads, writes and escapes.
        receiver = params[0].binding_id if literal.lifecycle is not None and params else None
        private = {p.binding_id for p in params if not p.place or p.binding_id == receiver}
        places = {p.binding_id: str(index) for index, p in enumerate(params) if p.place and p.binding_id != receiver}
        value_parameters = {p.binding_id for p in params if not p.place}
        word_bindings = set()
        pending = [literal.body]
        while pending:
            node = pending.pop()
            if isinstance(node, hir.FunctionLiteral):
                continue
            if isinstance(node, hir.Declare):
                private.add(node.binding_id)
            if isinstance(node, hir.IteratorExpression):
                private.add(node.target.binding_id)
                if word_iterator(node):
                    word_bindings.add(node.target.binding_id)
            pending.extend(hir.children(node))
        summary = rows.Contract(rows.Row())
        dependencies = []

        def contribute(contract):
            nonlocal summary
            summary = rows.join(summary, contract)

        def unknown():
            contribute(rows.Contract())

        def storage():
            # A logical storage obligation, including copies deferred by COW.
            # Until placement/move evidence is available here, an aggregate
            # value boundary conservatively needs allocation permission.
            contribute(rows.Contract(rows.Row((rows.Atom('allocates'),))))

        def word_value(node):
            return scalar(node.type) or (isinstance(node, hir.ExpressedIdentifier)
                                        and node.binding_id in word_bindings
                                        and ty.strip_refinement(node.type) in ('int', 'uint'))

        def location(node):
            path = bindings.access_path(node, unwrap=_unwrap)
            if path.binding_id in places:
                fields = tuple(step.name if isinstance(step, hir.MemberAccess) else '[]' for step in path.steps)
                return rows.Subject('parameter', places[path.binding_id], fields)
            if path.binding_id in private:
                return None
            return False  # unresolved external storage; distinct from private

        def access(node, family):
            subject = location(node)
            if subject is False:
                unknown()
            elif subject is not None:
                contribute(rows.Contract(rows.Row((rows.Atom(family, subject),))))
            path = bindings.access_path(node, unwrap=_unwrap)
            for step in path.steps:
                if isinstance(step, hir.Index):
                    visit(step.index)
            if not isinstance(path.root, hir.ExpressedIdentifier):
                visit(path.root)

        def call_subjects(node, signature):
            supplied = {}
            for index, param in enumerate([*signature.pos_or_kw, *signature.kw_only]):
                if not param.place:
                    continue
                argument = node.pos_args[index] if index < len(node.pos_args) else node.kw_args.get(param.name)
                if not isinstance(argument, hir.Place):
                    return None
                subject = location(argument.target)
                if subject is False:
                    return None
                supplied[str(index)] = subject
            return supplied

        def visit(node):
            if isinstance(node, hir.FunctionLiteral):
                return  # its body is checked at its own call boundary
            if isinstance(node, (hir.Void, hir.NoneValue, hir.Bool, hir.Integer, hir.String,
                                 hir.Break, hir.Continue, hir.ScopeMetatag, hir.TypeValue)):
                return
            if isinstance(node, hir.ExpressedIdentifier) and analysis._flatten_callable(node, frozenset()) is not None:
                return  # a statically known function handle has no storage read
            if isinstance(node, (hir.ExpressedIdentifier, hir.MemberAccess, hir.Index)):
                access(node, 'reads')
                return
            if isinstance(node, hir.Assert) and not node.runtime and not node.expect:
                return  # fact checking owns its purity/erasure boundary
            if isinstance(node, hir.FunctionCall):
                if node.proof:
                    return
                targets = analysis._direct_targets(node)
                if targets is not None:
                    for target in targets:
                        supplied = call_subjects(node, target.type)
                        if supplied is None:
                            unknown()
                        else:
                            dependencies.append((id(target), supplied))
                elif (isinstance(node.func, hir.ExpressedIdentifier) and node.func.binding_id is None
                      and node.func.name in SCALAR_OPERATIONS and scalar(node.type)
                      and all(word_value(arg) for arg in node.pos_args)):
                    pass
                elif isinstance(node.func.type, ty.FunctionType):
                    supplied = call_subjects(node, node.func.type)
                    if supplied is None:
                        unknown()
                    else:
                        contribute(rows.instantiate(node.func.type.effects or rows.Contract(), supplied))
                    visit(node.func)
                else:
                    unknown()
                for argument in [*node.pos_args, *node.kw_args.values()]:
                    if isinstance(argument, hir.Place):
                        # Address formation evaluates indices, not the value
                        # at the address. The callee supplies reads/writes.
                        path = bindings.access_path(argument.target, unwrap=_unwrap)
                        for step in path.steps:
                            if isinstance(step, hir.Index):
                                visit(step.index)
                        # The native frame-slot proof uses the same escape
                        # summaries. An unresolved callback may obey its
                        # public row, but currently provides no such storage
                        # proof, including through a forwarding helper.
                        if location(argument.target) is None and scalar(argument.target.type):
                            parameter_summaries = []
                            if targets is not None:
                                for target in targets:
                                    parameter = next((parameter for supplied, parameter in
                                                      analysis._pair_arguments(node, target) or ()
                                                      if supplied is argument), None)
                                    parameter_summaries.append(None if parameter is None else
                                                              storage_effects.for_param_binding(parameter.binding_id))
                            if not parameter_summaries or any(item is None or item.escapes for item in parameter_summaries):
                                storage()
                    else:
                        visit(argument)
                        if not word_value(argument) and not isinstance(argument.type, (ty.FunctionType, ty.OverloadType)):
                            storage()  # logical aggregate transfer not proved
                return
            if isinstance(node, hir.Declare):
                # A required view cannot silently allocate a replacement;
                # lowering must prove the storage demand or reject it.
                if not node.view and not scalar(node.expr.type) and not isinstance(node.expr, (hir.String, hir.FunctionLiteral)):
                    storage()
                visit(node.expr)
                return
            if isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign)):
                path = bindings.access_path(node.target, unwrap=_unwrap)
                # Projected writes may detach a shared array or require an
                # independent by-value parameter. Do not infer no allocation
                # merely because the final stored element is a scalar.
                projected_storage = (any(isinstance(step, hir.Index) for step in path.steps)
                                     or bool(path.steps) and path.binding_id in value_parameters)
                if not scalar(node.target.type) or projected_storage:
                    storage()
                access(node.target, 'mutates')
                if isinstance(node, hir.Assign) and node.op != '=':
                    access(node.target, 'reads')
                visit(node.value)
                return
            if isinstance(node, (hir.CopyValue, hir.ArrayLiteral, hir.ObjectLiteral)):
                if not scalar(node.type):
                    storage()
                for child in hir.children(node):
                    visit(child)
                return
            if isinstance(node, (hir.ValueCast, hir.RepresentationCast)) and not scalar(node.type):
                unknown()
                return
            if isinstance(node, hir.IteratorExpression):
                if not word_iterator(node):
                    unknown()
                for child in hir.children(node.iterable):
                    visit(child)
                return
            if isinstance(node, (hir.Block, hir.Suppress, hir.Return, hir.Flow, hir.IfArm, hir.LoopArm,
                                 hir.ShortCircuit, hir.Obligation, hir.TypeTest, hir.ArrayLength,
                                 hir.StringLength, hir.ValueCast, hir.RepresentationCast, hir.Spread,
                                 hir.MultiIteratorExpression)):
                for child in hir.children(node):
                    visit(child)
                return
            unknown()

        if not scalar(literal.rettype):
            storage()  # independent return storage; no placement proof yet
        visit(literal.body)
        for param in params:
            if isinstance(param, hir.BoundParam):
                visit(param.value)
        local[key] = summary
        calls[key] = dependencies
        for target, _ in dependencies:
            dependents.setdefault(target, set()).add(key)

    # Least fixed point of possible behaviors, independent of termination.
    # Calls translate parameter slots into the caller's storage routes. Deep
    # recursive routes widen positively; negative guarantees never widen.
    summaries = dict(local)
    pending = deque(local)
    queued = set(local)
    while pending:
        key = pending.popleft()
        queued.remove(key)
        updated = rows.join(local[key], *(rows.instantiate(summaries[target], supplied) for target, supplied in calls[key]))
        if rows.identity(updated) == rows.identity(summaries[key]):
            continue
        summaries[key] = updated
        for caller in dependents.get(key, ()):
            if caller not in queued:
                pending.append(caller)
                queued.add(caller)
    for literal in constrained:
        if not rows.implies(summaries[id(literal)], literal.type.effects):
            user_error(literal.source or srcfile, 'function does not satisfy its effect contract',
                       Pointer(span=literal.loc, message='an operation or callee may exceed the permitted effects or violate an exclusion'),
                       hint='omit the row to infer conservatively, or remove the operation requiring effects')
