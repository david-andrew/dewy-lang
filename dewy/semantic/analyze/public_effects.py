"""Conservative public-effect checking, starting with explicit empty rows.

This is not the aggregate-access analysis used for borrow selection. A local
read/write is private, whereas a place or captured mutable value belongs to
someone else. Unsupported storage operations remain unknown until their
allocation/escape behavior has a checked model; unknown never means pure.
"""
from collections import deque

from .. import effect_rows as rows, hir, ty
from ..errors import user_error
from ...reporting import Pointer
from .effects import _EffectAnalyzer, _literal_params

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


def validate(root, registry, srcfile):
    # Do not add a second whole-program fixed point to unannotated programs.
    constrained = [node for node in hir.walk(root) if isinstance(node, hir.FunctionLiteral)
                   and isinstance(node.type, ty.FunctionType) and node.type.effects is not None]
    if not constrained:
        return
    analysis = _EffectAnalyzer(root)
    summaries = {}
    edges = {}
    for literal in analysis.literals:
        key = id(literal)
        params = _literal_params(literal)
        private = {p.binding_id for p in params if not p.place}
        pending = [literal.body]
        while pending:
            node = pending.pop()
            if isinstance(node, hir.FunctionLiteral):
                continue
            if isinstance(node, hir.Declare):
                private.add(node.binding_id)
            pending.extend(hir.children(node))
        unknown = None
        dependencies = set()

        def visit(node):
            nonlocal unknown
            if unknown is not None:
                return
            if isinstance(node, hir.FunctionLiteral):
                return  # its body is checked at its own call boundary
            if isinstance(node, (hir.Void, hir.NoneValue, hir.Bool, hir.Integer, hir.String,
                                 hir.Break, hir.Continue, hir.ScopeMetatag, hir.TypeValue)):
                return
            if isinstance(node, hir.ExpressedIdentifier):
                if node.binding_id not in private:
                    unknown = node
                return
            if isinstance(node, hir.Assert) and not node.runtime and not node.expect:
                return  # fact checking owns its purity/erasure boundary
            if isinstance(node, hir.FunctionCall):
                if node.proof:
                    return
                targets = analysis._direct_targets(node)
                if targets is not None:
                    dependencies.update(id(target) for target in targets)
                elif (isinstance(node.func, hir.ExpressedIdentifier) and node.func.binding_id is None
                      and node.func.name in SCALAR_OPERATIONS and scalar(node.type)
                      and all(scalar(arg.type) for arg in node.pos_args)):
                    pass
                elif isinstance(node.func.type, ty.FunctionType) and rows.implies(node.func.type.effects, rows.Contract(rows.Row())):
                    visit(node.func)
                else:
                    unknown = node
                for argument in [*node.pos_args, *node.kw_args.values()]:
                    visit(argument)
                return
            if isinstance(node, hir.Declare):
                if not scalar(node.expr.type) and not isinstance(node.expr, (hir.String, hir.FunctionLiteral)):
                    unknown = node  # no promise about an implicit aggregate copy yet
                else:
                    visit(node.expr)
                return
            if isinstance(node, hir.Assign):
                if node.target.binding_id not in private or not scalar(node.target.type):
                    unknown = node
                else:
                    visit(node.value)
                return
            if isinstance(node, (hir.ValueCast, hir.RepresentationCast)) and not scalar(node.type):
                unknown = node
                return
            if isinstance(node, (hir.Block, hir.Suppress, hir.Return, hir.Flow, hir.IfArm, hir.LoopArm,
                                 hir.ShortCircuit, hir.Obligation, hir.TypeTest, hir.ArrayLength,
                                 hir.StringLength, hir.MemberAccess, hir.Index, hir.ValueCast,
                                 hir.RepresentationCast)):
                for child in hir.children(node):
                    visit(child)
                return
            unknown = node

        if not scalar(literal.rettype):
            unknown = literal  # escaping aggregate storage not modeled yet
        visit(literal.body)
        for param in params:
            if isinstance(param, hir.BoundParam):
                visit(param.value)
        summaries[key] = rows.Row(unknown=unknown is not None)
        for target in dependencies:
            edges.setdefault(target, set()).add(key)
    # Recursive calls may be effect-free without being terminating. That is
    # intentionally independent of the stricter $proof termination boundary.
    pending = deque(key for key, row in summaries.items() if row.unknown)
    while pending:
        target = pending.popleft()
        for caller in edges.get(target, ()):
            if not summaries[caller].unknown:
                summaries[caller] = rows.Row(unknown=True)
                pending.append(caller)
    for literal in constrained:
        if not rows.satisfies(summaries[id(literal)], literal.type.effects):
            user_error(literal.source or srcfile, 'function does not satisfy its effect contract',
                       Pointer(span=literal.loc, message='cannot establish `no_effects`: an operation or callee may have effects'),
                       hint='omit the row to infer conservatively, or remove the operation requiring effects')
