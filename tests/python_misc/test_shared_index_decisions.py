"""Emission facts on shared HIR must hold at every control-flow occurrence."""
import pytest
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.analyze import bounds

@pytest.mark.parametrize('upper', [2, 3])
@pytest.mark.parametrize('container,result,empty', [('array<int64>', 'int64', '0'), ('string', 'string', '""')])
def test_shared_index_does_not_keep_one_branch_constant(upper, container, result, empty):
    source = SrcFile(None, f'''$no_prelude=true
read=(@items:{container} index:int64<v=>0<=?v and v<?{upper}>):>{result}=>{{
if items.length<?{upper} return {empty}
if index=?0 return items[index]
return items[index]
}}''')
    root, context = check._typecheck_module(source)
    indices = [node for node in hir.walk(root) if isinstance(node, (hir.Index, hir.StringIndex))]
    assert len(indices) == 2
    shared, other = indices
    # Generated cleanup can reuse one selected route in multiple branches.
    # Keep both occurrence contexts, deliberately sharing just that HIR node.
    for node in hir.walk(root):
        if isinstance(node, hir.Return) and node.item is other:
            node.item = shared
    assert sum(node is shared for node in hir.walk(root)) == 2
    bounds.validate_bounds(root, context.binding_registry, source)
    assert shared.constant_index is None
