"""Keyword labels do not mutate a caller; argument evaluation still can."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

SOURCE = '''read=(values:set<int64>):>int64=>if 42 in? values 42 else 0
main=():>int64=>{
 let values:set<int64>=set[42]
 let answer:int64=0
 loop item in values {answer+=read(values=values)}
 return answer
}'''
CASES = [SOURCE, SOURCE.replace('values:set<int64>','values:dict<int64 int64>').replace('set[42]','[42 -> 42]').replace('loop item in values','loop [key item] in values')]
ERRORS = [
 SOURCE.replace('read(values=values)','read(values={values.clear(); set[42]})'),
 SOURCE.replace('read=(values:set<int64>):>int64=>if 42 in? values 42 else 0',
                'read=(@values:set<int64>):>int64=>{values.clear() return 42}').replace('read(values=values)','read(values=@values)'),
 SOURCE.replace('answer+=read(values=values)','values.clear()'),
]

@pytest.mark.parametrize('source', CASES)
def test_loop_keyword_label_is_not_a_write(tmp_path, source):
    execute(tmp_path,'keyword-loop',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_loop_keyword_value_keeps_writes(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source),debug_locations=False)


def test_native_loop_keyword_arguments(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
