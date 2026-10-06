"""Direct-call ownership inputs with one final consuming use.

This is a private calling convention, not a source effect or ownership tag.
Every caller materializes an independent argument and the callee owns it.
Earlier scalar observations can inspect the owned value, but cannot keep an
alias. Ordinary liveness still decides whether the final use can transfer.
"""
from collections import defaultdict, deque

from ...semantic import hir, ty, bindings
from ...semantic.analyze.effects import _literal_params
from ...semantic.analyze.predicate_effects import write_target
from ...semantic.analyze.storage_borrows import borrowable
from .borrowing import write_targets


def value_source(node):
    """Checked value wrappers preserve the consuming position of a read."""
    while True:
        if isinstance(node, hir.ValueCast) or (isinstance(node, hir.RepresentationCast)
                and ty.preserves_union_payload(node.expr.type, node.type)):
            node = node.expr
        elif isinstance(node, hir.Obligation):
            node = node.value
        elif isinstance(node, hir.Block) and len(node.items) == 1:
            node = node.items[0]
        else:
            return node


def owning_locals(literal):
    """Local stores worth donating into, excluding mere cursor rebinding.

    A read-only alias that is later replaced does not need an owning input
    protocol. Require an actual storage mutation or a whole-value transfer.
    Alias edges propagate that demand, but cannot create it by themselves.
    """
    needed, aliases = set(), defaultdict(set)
    def mark(value, *, route=False):
        source = value_source(value)
        if route:
            source = bindings.access_path(source, unwrap=value_source).root
        if isinstance(source, hir.ExpressedIdentifier) and source.binding_id is not None:
            needed.add(source.binding_id)
    pending = [literal.body]
    while pending:
        node = pending.pop()
        if isinstance(node, (hir.FunctionLiteral, hir.GenericFunction)):
            continue
        if isinstance(node, hir.Declare) and not node.view:
            source = value_source(node.expr)
            if isinstance(source, hir.ExpressedIdentifier) and source.binding_id is not None and node.binding_id is not None:
                aliases[node.binding_id].add(source.binding_id)
        elif isinstance(node, hir.Return) and node.item is not None:
            mark(node.item)
        elif isinstance(node, (hir.ObjectLiteral, hir.ArrayLiteral)):
            for child in hir.children(node):
                mark(child)
        elif isinstance(node, hir.Assign):
            # Native checking expands compound updates to `x = operation(x)`.
            # Keep that shape equivalent to an explicit compound assignment.
            if node.op != '=' or any(isinstance(read, hir.ExpressedIdentifier)
                    and read.binding_id == node.target.binding_id for read in hir.walk(node.value)):
                mark(node.target)
        elif isinstance(node, (hir.MemberAssign, hir.IndexAssign)):
            mark(node.target, route=True)
        elif isinstance(node, hir.FunctionCall):
            if isinstance(node.func, hir.ArrayMethod) and node.func.name in {'push', 'insert'} and node.pos_args:
                mark(node.pos_args[0])
            for argument in [*node.pos_args, *node.kw_args.values()]:
                if isinstance(argument, hir.Place):
                    mark(argument.target, route=True)
        if not isinstance(node, hir.IteratorExpression) and not (isinstance(node, hir.Assign) and node.op == '='):
            for target in write_targets(node):
                mark(target, route=True)
        pending.extend(hir.children(node))
    pending = list(needed)
    while pending:
        for source in aliases.get(pending.pop(), ()):
            if source not in needed:
                needed.add(source)
                pending.append(source)
    return needed


def parameters(analysis, excluded_literals, borrowed_literals=frozenset(), *,
               summaries=None, borrowed_bindings=frozenset()):
    """Find ordinary aggregate inputs donated into a value boundary or proved input.

    A worklist propagates only from actual consuming operations. A forwarding
    cycle without a consuming endpoint supplies no evidence. Functions used
    as values or capturing surrounding storage are excluded by the caller.
    """
    if summaries is None:
        summaries = analysis.solve()
    candidates = {}
    observation_cache = {}

    def observes(call, read):
        # Reuse the solved parameter effects: a scalar-returning known call
        # may inspect this argument, but may neither mutate nor retain it.
        if id(call) not in observation_cache:
            allowed = set()
            targets = analysis._direct_targets(call)
            shape = ty.structural_base(call.type)
            if (shape in ('bool', 'true', 'false') or ty.fixed_integer_layout(shape) is not None) and targets is not None and len(targets) == 1:
                for argument, parameter in analysis._pair_arguments(call, targets[0]) or ():
                    summary = summaries.for_param_binding(parameter.binding_id) if parameter is not None and parameter.binding_id is not None else None
                    if summary is not None and summary.read_only and not isinstance(argument, hir.Place):
                        allowed.add(id(value_source(argument)))
            observation_cache[id(call)] = allowed
        return id(read) in observation_cache[id(call)]

    for literal in analysis.literals:
        if id(literal) in excluded_literals or literal.object_receiver:
            continue
        wanted = {p.binding_id for p in _literal_params(literal)
                  if p.binding_id is not None and not p.place
                  and not isinstance(p, hir.BoundParam)
                  and isinstance(ty.structural_base(p.type), (ty.ObjectType, ty.TypeOr, ty.ArrayType))
                  and borrowable(p.type)}
        if not wanted:
            continue
        needed_locals = owning_locals(literal)
        # The route of an in-place change (`xs.push(v)`, `b.total+=n`) keeps
        # no alias of its root. The callee owns a donated input, so changing
        # it before the final consuming read only inspects it.
        mutated = set()
        for node in hir.walk(literal.body):
            route = None if isinstance(node, (hir.Assign, hir.Place)) else write_target(node)
            while route is not None:
                mutated.add(id(route))
                route = (route.value if isinstance(route, hir.MemberAccess)
                         else route.array if isinstance(route, hir.Index) else None)
        reads = defaultdict(list)
        # Per input: the fewest reads preceding an exit that reads it not at
        # all. A donation on such a path is simply released.
        bare_exits = {}
        def visit(node, parent=None, guarded=False, exposed=False, returning=None, lent=False, looped=False, observing=False):
            value = value_source(node)
            if value is not node:
                visit(value, parent, guarded, exposed, returning, lent, looped, observing)
                return
            if isinstance(node, hir.ExpressedIdentifier):
                if node.binding_id in wanted:
                    observed = not exposed and (
                        isinstance(parent, (hir.TypeTest, hir.ArrayLength))
                        # A scalar element read (`args[i]`) inspects the array.
                        or isinstance(parent, hir.Index) and value_source(parent.array) is node and (
                            ty.structural_base(parent.type) in ('bool', 'true', 'false')
                            or ty.fixed_integer_layout(parent.type) is not None)
                        or isinstance(parent, hir.FunctionCall) and observes(parent, node)
                        or (isinstance(parent, hir.MemberAccess) or
                            isinstance(parent, hir.ForwardingAccess) and parent.exception_type == ty.BOTTOM_TYPE) and (
                            ty.structural_base(parent.type) in ('bool', 'true', 'false')
                            or ty.fixed_integer_layout(parent.type) is not None))
                    # A place lent to a call ends when the call returns: the
                    # callee may change the input, never keep an alias of it.
                    observed = observed or lent and isinstance(parent, hir.Place)
                    # A field chain read only for a length or a scalar
                    # (`items.values.length`) is an inspection as well.
                    observed = observed or observing and not exposed or id(node) in mutated
                    reads[node.binding_id].append((node, parent, guarded, observed, returning, looped))
                return
            terminal = node
            if guarded:
                while isinstance(terminal, hir.Block) and terminal.items:
                    terminal = terminal.items[-1]
            if isinstance(terminal, hir.FunctionCall) and terminal.type == ty.BOTTOM_TYPE:
                # Diagnostics and other proved diverging calls cannot keep a
                # reader alive on the continuation that transfers this input.
                # The owning parameter remains valid until that call exits.
                return
            nested = guarded or isinstance(node, (hir.FunctionLiteral, hir.Flow,
                                                   hir.IfArm, hir.LoopArm, hir.ShortCircuit))
            exposed |= isinstance(node, (hir.FunctionLiteral, hir.Place, hir.Transmute,
                                          hir.Assign, hir.MemberAssign, hir.IndexAssign))
            counts = {binding: len(reads.get(binding, ())) for binding in wanted} if isinstance(node, hir.Return) else None
            if isinstance(node, hir.Return):
                returning = id(node)
            lends = isinstance(node, hir.Place) and isinstance(parent, hir.FunctionCall)
            # A loop body or a nested function may run a read many times.
            looping = looped or isinstance(node, (hir.LoopArm, hir.FunctionLiteral, hir.GenericFunction))
            # Field chains under a length or a scalar read inspect their root.
            inspecting = (isinstance(node, (hir.ArrayLength, hir.StringLength))
                          or isinstance(node, hir.MemberAccess) and (observing or ty.structural_base(node.type) in ('bool', 'true', 'false')
                                                                    or ty.fixed_integer_layout(node.type) is not None))
            for child in hir.children(node):
                visit(child, node, nested, exposed, returning, lends, looping,
                      inspecting and isinstance(child, (hir.MemberAccess, hir.ExpressedIdentifier)))
            if counts is not None:
                for binding, count in counts.items():
                    if len(reads.get(binding, ())) == count:
                        bare_exits[binding] = min(bare_exits.get(binding, count), count)

        # Defaults can execute conditionally. Do not ignore an additional
        # reference there even though the donating parameter has no default.
        for param in _literal_params(literal):
            if isinstance(param, hir.BoundParam):
                visit(param.value, guarded=True)
        visit(literal.body, literal)
        for binding, sites in reads.items():
            # Scalar inspections in guards/earlier loops create no surviving
            # loan. Early exits release the donated parameter normally. A
            # read inside another `return` ends its path before the final
            # read; it is accepted only when no exit before the final read
            # drops the input, so the donation is never released unused.
            # A final read inside a loop or conditional keeps the old fallback.
            final = sites[-1][4]
            returning_only = all(site[3] or site[4] is not None and site[4] != final for site in sites[:-1])
            inspected = all(site[3] for site in sites[:-1])
            # A final read inside a conditional `return` still runs at most
            # once and ends its path; other paths release the input.
            once = not sites[-1][2] or final is not None and not sites[-1][5]
            if once and (inspected or returning_only and bare_exits.get(binding, len(sites)) >= len(sites)):
                parent = sites[-1][1]
                if not isinstance(parent, hir.Declare) or parent.binding_id in needed_locals:
                    candidates[binding] = sites[-1][:2]

    proven = set()
    dependents = defaultdict(set)
    for binding, (read, parent) in candidates.items():
        if isinstance(parent, hir.ObjectLiteral) and id(parent) in borrowed_literals:
            # A proved call-root loan never owns these field handles. Its
            # construction is not a consumption endpoint for the parameter.
            continue
        if isinstance(parent, hir.Declare) and (parent.view or parent.binding_id in borrowed_bindings):
            continue  # a local loan is not an ownership boundary
        # A field, element or dictionary store keeps the value it stores.
        stored = (isinstance(parent, (hir.MemberAssign, hir.IndexAssign)) and value_source(parent.value) is read
                  or isinstance(parent, hir.DictStore) and parent.value is not None and value_source(parent.value) is read)
        if stored or isinstance(parent, (hir.Return, hir.ObjectLiteral, hir.ArrayLiteral, hir.Declare)) or (
                isinstance(parent, hir.FunctionLiteral) and value_source(parent.body) is read):
            shape = ty.structural_base(read.type)
            # Fixed-array calls can use prepared/raw storage, whose ownership
            # protocol is separate from a donated runtime descriptor.
            if not isinstance(shape, ty.ArrayType) or shape.length is None:
                proven.add(binding)
            continue
        if not isinstance(parent, hir.FunctionCall):
            continue
        if isinstance(parent.func, hir.ArrayMethod):
            if (parent.func.name in {'push', 'insert'} and parent.pos_args
                    and value_source(parent.pos_args[0]) is read):
                proven.add(binding)
            continue
        targets = analysis._direct_targets(parent)
        if targets is None or len(targets) != 1:
            continue
        for argument, parameter in analysis._pair_arguments(parent, targets[0]) or ():
            if value_source(argument) is read and parameter is not None and parameter.binding_id in candidates:
                dependents[parameter.binding_id].add(binding)
    pending = deque(proven)
    while pending:
        for binding in dependents.get(pending.popleft(), ()):
            if binding not in proven:
                proven.add(binding)
                pending.append(binding)
    return proven
