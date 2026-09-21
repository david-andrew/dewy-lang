"""Generated helper contracts must be proved, just like source-written ones."""
from dataclasses import replace
import pytest
from dewy.reporting import SrcFile, ReportException
from dewy.semantic import check, hir, ty
from dewy.semantic.analyze import bounds


def test_generated_clear_contract_rejects_a_body_that_does_not_clear():
    source = SrcFile(None, '''$no_prelude=true
Handle=type of [id:int64
$__drop__
release=():>void=>{}
]
clear=(@items:array<Handle>):>void=>items.clear
''')
    root = check.typecheck_and_resolve(source)
    helper = next(node for node in root.items if isinstance(node, hir.Declare) and node.name.startswith('__dewy_clear_array_'))
    # Remove the storage mutation while retaining its declared result fact.
    # A validator that trusts generated signatures would accept this body.
    body = replace(helper.expr.body, items=[
        hir.Void(node.loc, ty.VOID_TYPE) if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod) and node.func.name == 'clear' else node
        for node in helper.expr.body.items])
    changed = replace(helper, expr=replace(helper.expr, body=body))
    broken = replace(root, items=[changed if node is helper else node for node in root.items])
    with pytest.raises(ReportException, match='cannot prove|refinement refuted'):
        bounds.validate_bounds(broken, root.binding_registry, source)


def test_generated_array_copy_contract_rejects_a_body_that_does_not_append():
    source = SrcFile(None, '''$no_prelude=true
Handle=type of [id:int64
$__drop__
release=():>void=>{}
$__copy__
duplicate=():>Handle=>Handle[id]
]
copy=(@items:array<Handle>):>array<Handle>=>items.copy()
''')
    root = check.typecheck_and_resolve(source)
    helper = next(node for node in root.items if isinstance(node, hir.Declare)
                  and node.name.startswith('__dewy_copy_components_')
                  and isinstance(ty.strip_refinement(node.expr.rettype), ty.ArrayType))
    flow = next(node for node in helper.expr.body.items if isinstance(node, hir.Flow))
    arm = flow.arms[0]
    body = replace(arm.body, items=[node for node in arm.body.items
                                  if not (isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod))])
    changed_flow = replace(flow, arms=[replace(arm, body=body)])
    changed = replace(helper, expr=replace(helper.expr, body=replace(helper.expr.body,
        items=[changed_flow if node is flow else node for node in helper.expr.body.items])))
    broken = replace(root, items=[changed if node is helper else node for node in root.items])
    with pytest.raises(ReportException, match='cannot prove|refinement refuted'):
        bounds.validate_bounds(broken, root.binding_registry, source)


def test_generated_suffix_contract_rejects_a_body_that_changes_length():
    source = SrcFile(None, '''$no_prelude=true
Handle=type of [id:int64 $__drop__ release=():>void=>{}]
cut=(@items:array<Handle> count:int64<v=>v>=?0>):>void=>items.truncate(count)
''')
    root = check.typecheck_and_resolve(source)
    helper = next(node for node in root.items if isinstance(node, hir.Declare)
                  and node.name.startswith('__dewy_drop_array_')
                  and len(node.expr.pos_or_kw_args) == 3)
    param = helper.expr.pos_or_kw_args[0]
    receiver = hir.ExpressedIdentifier(helper.loc, param.type, param.name, binding_id=param.binding_id)
    method = hir.ArrayMethod(helper.loc, ty.FunctionType([], [], None, ty.VOID_TYPE), receiver, 'clear')
    changed = replace(helper, expr=replace(helper.expr, body=replace(helper.expr.body,
        items=[*helper.expr.body.items[:-1], hir.FunctionCall(helper.loc, ty.VOID_TYPE, method, [], {}),
               helper.expr.body.items[-1]])))
    broken = replace(root, items=[changed if node is helper else node for node in root.items])
    with pytest.raises(ReportException, match='cannot prove|refinement refuted'):
        bounds.validate_bounds(broken, root.binding_registry, source)
