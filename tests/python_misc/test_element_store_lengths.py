"""An element store preserves extents of all containing arrays, not its payload."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE='''change=(@rows:array<array<int64>>):>int64=>{
    if rows.length not=?1 or rows[0].length not=?2 return 1
    rows[0][0]=20
    return rows[0][0]+rows[0][1]
}
main=():>int64=>{let rows:array<array<int64>>=[[1 22]] return change(@rows)}
'''
DEEP=SOURCE.replace('array<array<int64>>', 'array<array<array<int64>>>')
DEEP=DEEP.replace('rows[0].length not=?2', 'rows[0].length not=?1 or rows[0][0].length not=?2')
DEEP=DEEP.replace('rows[0][0]=20', 'rows[0][0][0]=20').replace('return rows[0][0]+rows[0][1]', 'return rows[0][0][0]+rows[0][0][1]')
DEEP=DEEP.replace('=[[1 22]]', '=[[[1 22]]]')
SELECTED=SOURCE.replace('>>):>', '>> i:addr):>').replace('rows[0]', 'rows[i]')
SELECTED=SELECTED.replace('rows.length not=?1', 'i>=?rows.length').replace('change(@rows)', 'change(@rows 0)')
CASES=[SOURCE,DEEP,SELECTED]
ERRORS=[SOURCE.replace('rows[0][0]=20', 'rows[0]=[20]'),
    SOURCE.replace('change=','replace=(@rows:array<array<int64>>):>int64=>{rows[0]=[20] return 20}\nchange=')
          .replace('rows[0][0]=20', 'rows[0][0]=replace(@rows)'),
]
# Establish only the precondition needed to write the replacement's row.
ERRORS[1]=ERRORS[1].replace('=>{rows[0]=[20]', '=>{if rows.length=?0 return 0\nrows[0]=[20]')

@pytest.mark.parametrize('source', CASES)
def test_element_store_preserves_containing_lengths(tmp_path, source):
    execute(tmp_path, 'element-length', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_replaced_elements_and_rhs_effects_invalidate_lengths(source):
    with pytest.raises(ReportException, match='bounds|index'):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_element_store_lengths(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
