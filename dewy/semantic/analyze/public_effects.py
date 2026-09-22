"""Infer public callable effects and check selected source contracts.

This is not the aggregate-access analysis used for borrow selection. A local
read/write is private, whereas a place or captured mutable value belongs to
someone else. Unsupported storage operations remain unknown until their
allocation/escape behavior has a checked model; unknown never means pure.
"""

from .. import bindings, effect_rows as rows, effect_inference as inference, hir, ty, placement
from ..errors import user_error
from ...reporting import Pointer
from .effects import _EffectAnalyzer, _literal_params, _unwrap, place_loans
from . import storage_borrows

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


def inventory(root, registry):
    """Collect finite body/call equations; keep call environments until solving."""
    analysis = _EffectAnalyzer(root)
    storage_effects = analysis.solve()
    frame_places = place_loans(analysis, storage_effects)
    storage_proofs = storage_borrows.prove(analysis, storage_effects)
    borrowed_arguments = storage_proofs.arguments
    local = {}
    projections = {}

    def instantiate(contract, supplied):
        if not supplied:
            return contract
        # A call owns one equation. Recursive calls reference body variables,
        # never an ever-growing string of composed substitution environments.
        name = inference.PREFIX + f'call:{len(projections)}'
        projections[name] = inference.Projection(contract, supplied)
        return rows.Contract(rows.Row(variables=(name,)))
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
        frame_values = placement.local_values(literal, frame_places.nonescaping, frame_places.fixed_storage, borrowed_arguments)
        frame_literals = set().union(*(placement.literal_storage(node.expr) for node in frame_values.values()))
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
            path = bindings.access_path(node, unwrap=_unwrap, dictionaries=True)
            for step in path.steps:
                if isinstance(step, hir.DictLookup):
                    # A key selection searches the containing dictionary.
                    # Do not expose its hidden values array as a narrower
                    # public permission, or pretend keys are not read.
                    return location(step.keys.value) if isinstance(step.keys, hir.MemberAccess) else False
            if path.binding_id in places:
                fields = tuple(step.name if isinstance(step, hir.MemberAccess) else '[]' for step in path.steps)
                return rows.Subject('parameter', places[path.binding_id], fields)
            if path.binding_id in private:
                return None
            if isinstance(path.root, (hir.FunctionCall, hir.ObjectLiteral, hir.ArrayLiteral, hir.CopyValue, hir.Block, hir.Flow)):
                # A computed value owns its result. Evaluating that result
                # still contributes effects through access's root visit.
                return None
            return False  # unresolved external storage; distinct from private

        def access(node, family):
            subject = location(node)
            if subject is False:
                unknown()
            elif subject is not None:
                contribute(rows.Contract(rows.Row((rows.Atom(family, subject),))))
            path = bindings.access_path(node, unwrap=_unwrap, dictionaries=True)
            for step in path.steps:
                if isinstance(step, hir.Index):
                    visit(step.index)
                elif isinstance(step, hir.DictLookup):
                    access(step.keys.value, 'reads')
                    visit(step.key)
                    storage()
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

        def callback(value):
            # Sort invokes a value parameter for each selected element. Its
            # body participates in the same equations as an ordinary call;
            # evaluating a function handle alone does not account for that.
            targets = analysis._value_targets(value)
            if targets is not None:
                for target in targets:
                    if any(param.place for param in _literal_params(target)):
                        unknown()
                    else:
                        contribute(rows.Contract(rows.Row(variables=(body_name(id(target)),))))
            elif isinstance(value.type, ty.FunctionType) and not any(param.place for param in [*value.type.pos_or_kw, *value.type.kw_only]):
                contribute(value.type.effects or rows.Contract())
            else:
                unknown()

        def projected_storage(path):
            # Mutating a projection can detach its owning aggregate. The
            # obligation is the same for a store and a forwarded place.
            return path.binding_id not in frame_values and (
                any(isinstance(step, (hir.Index, hir.DictLookup)) for step in path.steps)
                or bool(path.steps) and path.binding_id in value_parameters)

        def visit(node):
            if isinstance(node, hir.ValueCast) and node.effect_target is not None:
                visit(node.expr)
                return
            if isinstance(node, hir.FunctionLiteral):
                return  # its body is checked at its own call boundary
            if isinstance(node, (hir.Void, hir.NoneValue, hir.Bool, hir.Integer, hir.String,
                                 hir.Break, hir.Continue, hir.ScopeMetatag, hir.TypeValue)):
                return
            if isinstance(node, hir.ExpressedIdentifier) and analysis._value_targets(node) is not None:
                return  # a statically known function handle has no storage read
            if isinstance(node, (hir.ExpressedIdentifier, hir.MemberAccess, hir.Index)):
                access(node, 'reads')
                return
            if isinstance(node, hir.Assert) and not node.runtime and not node.expect:
                return  # fact checking owns its purity/erasure boundary
            if isinstance(node, hir.FunctionCall):
                if node.proof:
                    return
                if isinstance(node.func, hir.ArrayMethod) and node.func.name in {'push', 'pop', 'insert', 'truncate', 'clear', 'reserve', 'join', 'sort'}:
                    # Growth, detachment, returned storage and implicit value
                    # copies need permission. COW postponement is not proof of
                    # no allocation. Lifecycle calls added later are checked
                    # again. Sort additionally invokes its key callback.
                    access(node.func.array, 'reads')
                    if node.func.name != 'join':
                        access(node.func.array, 'mutates')
                    storage()
                    if node.func.name == 'sort' and (key := node.kw_args.get('key')) is not None:
                        callback(key)
                    for argument in [*node.pos_args, *node.kw_args.values()]:
                        visit(argument)
                    return
                targets = analysis._direct_targets(node)
                if targets is not None:
                    # Resolving the result does not erase selector evaluation.
                    visit(node.func)
                    for target in targets:
                        supplied = call_subjects(node, target.type)
                        if supplied is None:
                            unknown()
                        else:
                            contribute(instantiate(rows.Contract(rows.Row(variables=(body_name(id(target)),))), supplied))
                elif (isinstance(node.func, hir.ExpressedIdentifier) and node.func.binding_id is None
                      and node.func.name in SCALAR_OPERATIONS and scalar(node.type)
                      and all(word_value(arg) for arg in node.pos_args)):
                    pass
                elif isinstance(node.func.type, ty.FunctionType):
                    supplied = call_subjects(node, node.func.type)
                    if supplied is None:
                        unknown()
                    else:
                        contribute(instantiate(node.func.type.effects or rows.Contract(), supplied))
                    visit(node.func)
                else:
                    unknown()
                for argument in [*node.pos_args, *node.kw_args.values()]:
                    if isinstance(argument, hir.Place):
                        # Address formation evaluates indices, not the value
                        # at the address. The callee supplies reads/writes.
                        path = bindings.access_path(argument.target, unwrap=_unwrap, dictionaries=True)
                        for step in path.steps:
                            if isinstance(step, hir.Index):
                                visit(step.index)
                            elif isinstance(step, hir.DictLookup):
                                access(step.keys.value, 'reads')
                                visit(step.key)
                                storage()  # selecting a mutable entry can detach storage
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
                            elif projected_storage(path) and any(item.writes for item in parameter_summaries):
                                storage()
                    else:
                        visit(argument)
                        if (not word_value(argument) and not isinstance(argument.type, (ty.FunctionType, ty.OverloadType))
                                and id(argument) not in borrowed_arguments.get(id(node), ())):
                            storage()  # logical aggregate transfer not proved
                return
            if isinstance(node, (hir.DictLookup, hir.DictContains, hir.DictStore, hir.DictRemove)):
                # keys/values are implementation projections of one receiver.
                # Model that receiver once, and keep eager default/argument
                # evaluation even when the entry is known to exist.
                if not isinstance(node.keys, hir.MemberAccess):
                    unknown()
                    return
                access(node.keys.value, 'reads')
                if isinstance(node, (hir.DictStore, hir.DictRemove)):
                    access(node.keys.value, 'mutates')
                # A lazy index rebuild/compaction may allocate even on reads.
                # Proved positions are not used as a public no-allocation
                # promise; subsequent lowering can invalidate cached slots.
                storage()
                for name in ('key', 'value', 'default'):
                    argument = getattr(node, name, None)
                    if argument is not None:
                        visit(argument)
                return
            if isinstance(node, (hir.DictView, hir.DictEntries)):
                access(node.dictionary, 'reads')
                storage()
                return
            if isinstance(node, hir.SetAlgebra):
                visit(node.left)
                visit(node.right)
                storage()
                return
            if isinstance(node, hir.Declare):
                # A required view cannot silently allocate a replacement;
                # lowering must prove the storage demand or reject it.
                if not node.view and node.binding_id not in storage_proofs.local_views and node.binding_id not in frame_values and not scalar(node.expr.type) and not isinstance(node.expr, (hir.String, hir.FunctionLiteral)) and not isinstance(node.expr.type, (ty.FunctionType, ty.OverloadType)):
                    storage()
                visit(node.expr)
                return
            if isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign)):
                path = bindings.access_path(node.target, unwrap=_unwrap, dictionaries=True)
                # Projected writes may detach a shared array or require an
                # independent by-value parameter. Do not infer no allocation
                # merely because the final stored element is a scalar.
                if (not scalar(node.target.type) and not isinstance(node.target.type, (ty.FunctionType, ty.OverloadType))) or projected_storage(path):
                    storage()
                access(node.target, 'mutates')
                if isinstance(node, hir.Assign) and node.op != '=':
                    access(node.target, 'reads')
                visit(node.value)
                return
            if isinstance(node, (hir.CopyValue, hir.ArrayLiteral, hir.ObjectLiteral)):
                if not scalar(node.type) and id(node) not in frame_literals:
                    storage()
                for child in hir.children(node):
                    visit(child)
                return
            if (isinstance(node, (hir.ValueCast, hir.RepresentationCast)) and ty.string_valued(node.type)
                    and ty.string_valued(node.expr.type)):
                # String/character/literal widening preserves the stored text;
                # value boundaries account for any independent ownership.
                visit(node.expr)
                return
            if isinstance(node, hir.ValueCast) and ty.structural_base(node.type) == ty.structural_base(node.expr.type):
                # A proved refinement retains the same storage. Its value
                # boundary, if any, already owns the copy/allocation demand.
                visit(node.expr)
                return
            if isinstance(node, (hir.ValueCast, hir.RepresentationCast)) and ty.structural_base(node.expr.type) == 'none':
                # The absent union arm has no payload; its cell needs no heap.
                visit(node.expr)
                return
            if isinstance(node, (hir.ValueCast, hir.RepresentationCast)) and not scalar(node.type):
                unknown()
                return
            if isinstance(node, hir.IteratorExpression):
                if word_iterator(node):
                    for child in hir.children(node.iterable):
                        visit(child)
                elif isinstance(ty.structural_base(node.iterable.type), ty.ArrayType):
                    storage()
                    visit(node.iterable)
                else:
                    unknown()
                    visit(node.iterable)
                return
            if isinstance(node, (hir.Block, hir.Suppress, hir.Return, hir.Flow, hir.IfArm, hir.LoopArm, hir.OverloadedFunction,
                                 hir.ShortCircuit, hir.Obligation, hir.TypeTest, hir.ArrayLength,
                                 hir.StringLength, hir.ValueCast, hir.RepresentationCast, hir.Spread,
                                 hir.MultiIteratorExpression)):
                for child in hir.children(node):
                    visit(child)
                return
            unknown()

        if not scalar(literal.rettype) and not isinstance(literal.rettype, (ty.FunctionType, ty.OverloadType)):
            storage()  # independent return storage; no placement proof yet
        visit(literal.body)
        for param in params:
            if isinstance(param, hir.BoundParam):
                visit(param.value)
        local[key] = summary
    return local, projections


def body_name(key):
    return inference.PREFIX + f'body:{key}'


def summarize(root, registry):
    """Infer bodies without value-boundary constraints, for analysis clients."""
    local, projections = inventory(root, registry)
    solutions = inference.solve_contracts({body_name(key): body for key, body in local.items()},
                                          projections=projections)
    return {key: solutions[body_name(key)] for key in local}


def validate(root, registry, srcfile):
    # Do not add a second whole-program fixed point to unannotated programs.
    constrained = [node for node in hir.walk(root) if isinstance(node, hir.FunctionLiteral)
                   and isinstance(node.type, ty.FunctionType) and node.type.effects is not None]
    if not constrained:
        return
    definitions = {}
    bodies = []
    boundaries = []
    for node in hir.walk(root):
        if isinstance(node, hir.FunctionLiteral) and node.type.inferred_effect is not None:
            name = node.type.inferred_effect
            bodies.append((name, node))
        elif isinstance(node, hir.ValueCast):
            if node.effect_target is not None and isinstance(node.effect_target, ty.FunctionType) and node.effect_target.effects is not None and node.effect_target.effects.allowed is not None:
                for name in node.effect_target.effects.allowed.variables:
                    if name.startswith(inference.BINDING_PREFIX):
                        definitions.setdefault(name, rows.Contract(rows.Row()))
            boundaries.extend((node, edge) for edge in inference.type_constraints(node.expr.type, node.effect_target or node.type))
    written = any(node.type.inferred_effect is None for node in constrained)
    required = any(edge.required is not None and not rows.implies(None, edge.required)
                   and (not inference.pending(edge.required) or edge.required.excluded)
                   for _, edge in boundaries)
    if not written and not required:
        return
    summaries, projections = inventory(root, registry)
    definitions.update((body_name(key), body) for key, body in summaries.items())
    for name, node in bodies:
        body = rows.Contract(rows.Row(variables=(body_name(id(node)),)))
        definitions[name] = rows.join(definitions[name], body) if name in definitions else body
    # Written exclusions seed the finite qualifier vocabulary. They are
    # obligations, never positive lower bounds on an unrelated row variable.
    requirements = tuple(inference.Constraint(None, rows.Contract(excluded=node.type.effects.excluded))
                         for node in constrained if node.type.effects.excluded)
    solutions = inference.solve_contracts(definitions, tuple(edge for _, edge in boundaries) + requirements, projections)
    for node, edge in boundaries:
        if not inference.satisfied_contracts(edge, solutions):
            user_error(srcfile, 'callable does not satisfy its effect contract',
                       Pointer(span=node.loc, message='the inferred callable behavior exceeds its destination contract'))
    for literal in constrained:
        if not rows.implies(solutions[body_name(id(literal))], inference.resolve_contracts(literal.type.effects, solutions)):
            user_error(literal.source or srcfile, 'function does not satisfy its effect contract',
                       Pointer(span=literal.loc, message='an operation or callee may exceed the permitted effects or violate an exclusion'),
                       hint='omit the row to infer conservatively, or remove the operation requiring effects')
