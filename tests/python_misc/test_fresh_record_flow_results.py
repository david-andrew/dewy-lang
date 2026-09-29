"""A conditional adopts an explicit copy's owner without copying it again."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute
from test_copied_record_moves import SOURCE as BASE

SOURCE=BASE.replace('let copied=input.copy()',
                    'let copied=if input.items.length>?0 input.copy() else Box[[]]')
CASES=[SOURCE,
       SOURCE.replace('input.copy() else Box[[]]', '{input.copy()} else Box[[]]'),
       SOURCE.replace('let copied=if input.items.length>?0 input.copy() else Box[[]]',
                      'let copied=if input.items.length=?0 Box[[]] else input.copy()'),
       SOURCE.replace('Box:type=', 'Box=type of ')]
REJECTED=SOURCE.replace('input.copy()', 'input')

@pytest.mark.parametrize('source',CASES)
def test_fresh_record_flow_result(tmp_path,source):
    execute(tmp_path,'fresh-record-flow',codegen(SrcFile(None,source),debug_locations=False))

def test_live_record_flow_result_still_requires_a_copy():
    with pytest.raises(ReportException,match='unproven copy'):
        codegen(SrcFile(None,REJECTED),debug_locations=False)

def test_native_fresh_record_flow_results(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=[REJECTED])
