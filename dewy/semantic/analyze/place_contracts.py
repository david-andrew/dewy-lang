"""A borrowed nominal parent must preserve the complete child's identity.

The checker establishes compatible writable field contracts. This pass uses
the transitive access summaries to rule out whole-value replacement and
escape through that wider view. Unknown callbacks cannot provide that proof.
"""
from .. import hir, ty
from ..errors import user_error
from ...reporting import Pointer
from .effects import _EffectAnalyzer


def parent_arguments(call):
    signature = call.func.type
    if isinstance(signature, ty.OverloadType):
        methods = signature.methods if call.selected_method_index is None else [signature.methods[call.selected_method_index]]
    else:
        methods = [signature] if isinstance(signature, ty.FunctionType) else []
    arguments = {}
    for signature in methods:
        parameters = {p.name: p for p in [*signature.pos_or_kw, *signature.kw_only]}
        positional = [p for p in signature.pos_or_kw if p.name not in call.kw_args]
        pairs = [*zip(positional, call.pos_args),
                 *((parameters[name], arg) for name, arg in call.kw_args.items() if name in parameters)]
        for parameter, argument in pairs:
            if (parameter.place and isinstance(argument, hir.Place) and argument.type != parameter.type
                    and ty.user_branded(ty.unfold(ty.strip_refinement(argument.type)))):
                arguments[id(argument)] = argument
    return list(arguments.values())


def validate(root, registry, srcfile):
    candidates = []
    pending = [(root, srcfile)]
    seen = set()
    while pending:
        node, source = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, hir.FunctionLiteral):
            source = node.source or source
        if isinstance(node, hir.FunctionCall) and (arguments := parent_arguments(node)):
            candidates.append((node, arguments, source))
        if isinstance(node, hir.Program):
            pending.extend(zip(node.items, node.item_sources))
        else:
            pending.extend((child, source) for child in hir.children(node))
    if not candidates:
        return
    analysis = _EffectAnalyzer(root)
    effects = analysis.solve()
    for call, arguments, source in candidates:
        targets = analysis._direct_targets(call)
        for argument in arguments:
            safe = targets is not None
            for target in targets or ():
                parameter = next((parameter for supplied, parameter in analysis._pair_arguments(call, target) or ()
                                  if supplied is argument), None)
                summary = None if parameter is None else effects.for_param_binding(parameter.binding_id)
                if summary is None or () in summary.rebinds or () in summary.escapes:
                    safe = False
                    break
            if not safe:
                user_error(source, 'parent place may replace or escape the child',
                           Pointer(span=argument.loc, message='the complete child must retain its identity through this parent view'),
                           hint='update the parent fields without replacing or retaining the whole parent place')
