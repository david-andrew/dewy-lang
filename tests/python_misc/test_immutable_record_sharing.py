"""Sharing an immutable record is not a costly copy under `$explicit_copies`.

Nothing writes through a `const` record, so its copy defers no detach (the
same bound as sharing a string). A writable record of the same shape still
needs an explicit copy or a proof.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

BODY = '''
keep=(row:Row):>int64=>{
 let rows:array<Row>=[]
 rows.push(row)
 if rows.length<?1 or rows[0].values.length<?1 or row.values.length<?1 return 1
 return rows[0].values[0]+row.values[0]-42
}
main=():>int64=>keep(Row[[42] 'row'])'''
CASES = ['$explicit_copies\nRow:type=const [values:array<int64> name:string]' + BODY,
         '$explicit_copies\nRow:type=const [values:array<int64> name:string]\nBox:type=const [row:Row]' + BODY.replace(
             'main=():>int64=>keep(Row[[42] \'row\'])', 'main=():>int64=>keep(Box[Row[[42] \'row\']].row)')]
ERRORS = ['$explicit_copies\nRow:type=[values:array<int64> name:string]' + BODY]


@pytest.mark.parametrize('source', CASES)
def test_immutable_record_share_is_accepted(tmp_path, source):
    execute(tmp_path, 'immutable-share', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_writable_record_copy_stays_explicit(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_immutable_record_sharing(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
