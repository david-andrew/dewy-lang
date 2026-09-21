"""Checked proof declarations and their deliberately small initial language.

Proofs reuse ordinary fact obligations, but are not ordinary void functions.
This pass checks the erasure boundary before bounds validation: statements,
pure fact arguments, a finite body, and an acyclic graph of known proofs.
"""
from dataclasses import fields, replace

from ..reporting import Pointer, SrcFile
from . import bindings, hir, ty
from .errors import user_error


OPERATIONS = frozenset({
    '__add__', '__sub__', '__mul__', '__unary_sub__', '__not__',
    '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__',
    '__and__', '__or__', '__xor__', '__nand__', '__nor__', '__xnor__',
})


def fact_term(node: hir.AST, parameters: set[int] | None = None) -> bool:
    if isinstance(node, hir.ExpressedIdentifier):
        return node.binding_id is not None and (parameters is None or node.binding_id in parameters)
    if isinstance(node, (hir.Integer, hir.Bool)):
        return True
    if isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
        return fact_term(node.expr, parameters)
    if isinstance(node, hir.Obligation):
        return fact_term(node.value, parameters)
    if isinstance(node, (hir.ArrayLength, hir.StringLength, hir.MemberAccess)):
        value = node.array if isinstance(node, hir.ArrayLength) else node.string if isinstance(node, hir.StringLength) else node.value
        return fact_term(value, parameters)
    if isinstance(node, hir.TypeTest):
        return fact_term(node.value, parameters)
    if isinstance(node, hir.ShortCircuit):
        return fact_term(node.left, parameters) and fact_term(node.right, parameters)
    if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
        return fact_term(node.items[0], parameters)
    if isinstance(node, hir.FunctionCall) and not node.proof and not node.kw_args:
        callee = node.func
        return (isinstance(callee, hir.ExpressedIdentifier) and callee.binding_id is None
                and callee.name in OPERATIONS and all(fact_term(arg, parameters) for arg in node.pos_args))
    return False


def validate(root: hir.AST, registry: bindings.BindingRegistry, source: SrcFile) -> None:
    if not any(binding.proof for binding in registry.by_id.values()):
        return
    functions: dict[int, hir.FunctionLiteral] = {}
    edges: dict[int, set[int]] = {}

    def fail(node: hir.AST, title: str, detail: str, src: SrcFile) -> None:
        user_error(src, title, Pointer(span=node.loc, message=detail))

    def call(node: hir.FunctionCall, src: SrcFile, parameters: set[int] | None = None) -> int:
        target = registry.by_id.get(node.func.binding_id) if isinstance(node.func, hir.ExpressedIdentifier) else None
        if target is None or not target.proof:
            fail(node, 'a proof requires a known direct callee', 'proofs cannot be called through a callback or stored handle', src)
        for arg in [*node.pos_args, *node.kw_args.values()]:
            if not fact_term(arg, parameters):
                fail(arg, 'a proof argument must be a pure fact term', 'use a name, literal, trusted measure, or arithmetic over those; the call is erased', src)
        return target.id

    def proof_body(node: hir.AST, parameters: set[int], dependencies: set[int], src: SrcFile) -> None:
        if isinstance(node, hir.Block):
            for item in node.items:
                proof_body(item, parameters, dependencies, src)
        elif isinstance(node, hir.Void):
            pass
        elif isinstance(node, hir.Suppress):
            proof_body(node.item, parameters, dependencies, src)
        elif isinstance(node, hir.Return) and node.item is None:
            pass
        elif isinstance(node, hir.Obligation):
            proof_body(node.value, parameters, dependencies, src)
        elif isinstance(node, hir.Assert) and not node.runtime and not node.expect and not node.unsafe:
            if not fact_term(node.condition, parameters):
                fail(node, 'a proof assertion must use pure fact terms', 'proofs cannot read mutable globals or call runtime functions', src)
        elif isinstance(node, hir.FunctionCall) and node.proof:
            dependencies.add(call(node, src, parameters))
        elif isinstance(node, hir.Flow) and all(isinstance(arm, hir.IfArm) for arm in node.arms):
            for arm in node.arms:
                if not fact_term(arm.condition, parameters):
                    fail(arm.condition, 'a proof condition must use pure fact terms', 'runtime evaluation cannot be erased', src)
                proof_body(arm.body, parameters, dependencies, src)
            if node.default is not None:
                proof_body(node.default, parameters, dependencies, src)
        else:
            fail(node, 'unsupported operation in a checked proof', 'the initial terminating subset permits assertions, branches, and direct calls of other proofs', src)

    def visit(node: hir.AST, statement: bool, src: SrcFile) -> None:
        if isinstance(node, hir.FunctionLiteral):
            src = node.source or src
            if node.proof:
                params = [*node.pos_or_kw_args, *node.kw_only_args]
                if node.rest_args is not None or any(p.place or isinstance(p, hir.BoundParam) for p in params):
                    fail(node, 'proof parameters must be explicit values', 'place, default, and rest parameters are outside the initial proof subset', src)
                dependencies: set[int] = set()
                proof_body(node.body, {p.binding_id for p in params if p.binding_id is not None}, dependencies, src)
            visit(node.body, True, src)
            return
        if isinstance(node, hir.Declare) and isinstance(node.expr, hir.FunctionLiteral) and node.expr.proof:
            if node.binding_id is not None:
                functions[node.binding_id] = node.expr
                edges[node.binding_id] = {call(n, node.expr.source or src) for n in hir.walk(node.expr.body) if isinstance(n, hir.FunctionCall) and n.proof}
        if isinstance(node, hir.FunctionCall) and node.proof:
            if not statement:
                fail(node, 'a proof call is a statement, not a value', 'do not bind, return, or pass its result', src)
            call(node, src)
            return  # the direct callee identifier is the one allowed proof reference
        if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
            binding = registry.by_id.get(node.binding_id)
            if binding is not None and binding.proof:
                fail(node, 'a proof function is not a value', 'only direct statement calls are supported', src)
        if isinstance(node, hir.Block):
            for item in node.items:
                visit(item, True, src)
        elif isinstance(node, hir.Flow):
            for arm in node.arms:
                visit(arm.condition, False, src)
                visit(arm.body, statement, src)
            if node.default is not None:
                visit(node.default, statement, src)
        elif isinstance(node, hir.Suppress):
            visit(node.item, statement, src)
        elif isinstance(node, hir.Obligation):
            visit(node.value, statement, src)
        else:
            for child in hir.children(node):
                visit(child, False, src)

    visit(root, True, source)
    active: set[int] = set()
    checked: set[int] = set()

    def acyclic(binding: int) -> None:
        if binding in checked or binding not in functions:
            return  # imported proof bodies were checked with their defining module
        function = functions[binding]
        if binding in active:
            fail(function, 'a checked proof cannot depend on itself', 'the initial proof-call graph must be acyclic', function.source or source)
        active.add(binding)
        for dependency in edges[binding]:
            acyclic(dependency)
        active.remove(binding)
        checked.add(binding)

    for binding in functions:
        acyclic(binding)


def erase(root: hir.AST) -> hir.AST:
    """Erase proof constructs and checked effect boundaries after obligations pass."""
    def rewrite(value):
        if isinstance(value, hir.ValueCast) and value.effect_target is not None:
            return rewrite(value.expr)
        if isinstance(value, hir.FunctionCall) and value.proof:
            return hir.Void(value.loc, ty.VOID_TYPE)
        if isinstance(value, hir.Declare) and isinstance(value.expr, hir.FunctionLiteral) and value.expr.proof:
            return hir.Void(value.loc, ty.VOID_TYPE)
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, tuple):
            return tuple(rewrite(item) for item in value)
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, (hir.AST, hir.Param, hir.ObjectField)):
            changes = {f.name: rewrite(getattr(value, f.name)) for f in fields(value) if f.name in hir.child_fields(type(value))}
            return replace(value, **changes) if changes else value
        return value
    # Most modules contain no proofs; don't rebuild their trees unnecessarily.
    if not any(isinstance(node, hir.FunctionCall) and node.proof or isinstance(node, hir.FunctionLiteral) and node.proof or isinstance(node, hir.ValueCast) and node.effect_target is not None for node in hir.walk(root)):
        return root
    return rewrite(root)
