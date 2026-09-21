"""Lowering may reuse checked programs without consuming their proof metadata."""
from dewy.backend.udewy.emit import codegen_inner
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from tests.python_misc.test_scalar_projection import execute


def test_repeated_lowering_preserves_checked_parameter_facts(tmp_path):
    source = SrcFile(None, '''
read=(index:addr):>addr=>index
main=():>int64=>read(42) as int64
''')
    root = check.typecheck_and_resolve(source, include_prelude=True)
    function = next(node.expr for node in root.items if isinstance(node, hir.Declare) and node.name == 'read')
    parameter = function.pos_or_kw_args[0]
    assert isinstance(parameter.type, ty.RefinedType)
    original_type = parameter.type
    first = codegen_inner(root, source, debug_locations=False)
    assert parameter.type is original_type
    second = codegen_inner(root, source, debug_locations=False)
    assert parameter.type is original_type
    assert first == second
    execute(tmp_path, 'reused-checked-graph', second)
