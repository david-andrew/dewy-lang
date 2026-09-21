"""Truncation transfers min(length, count), including symbolic operands."""
import pytest
from dewy.reporting import SrcFile, ReportException
from dewy.backend.udewy import codegen
from tests.python_misc.test_scalar_projection import execute

CASES = [
    '''cap=(@xs:array<int64> count:int64<v=>0<=?v<=?xs.length>):>void & <xs.length=?count>=>{xs.truncate(count)}
main=():>int64=>{let xs:array<int64>=[40 2 9] cap(@xs 2) $assert xs.length=?2 return xs[0]+xs[1]}''',
    '''cap=(@xs:array<int64> count:int64<v=>v>=?0>):>void & <xs.length<=?count>=>{xs.truncate(count)}
main=():>int64=>{let xs:array<int64>=[42] cap(@xs 10) return 42}''',
    '''keep=(@xs:array<int64> count:int64<v=>v>=?xs.length> i:int64<v=>0<=?v<?xs.length>):>int64=>{
xs.truncate(count) return xs[i]}
main=():>int64=>{let xs:array<int64>=[42] return keep(@xs 10 0)}''',
    '''keep=(@xs:array<int64> i:int64<v=>0<=?v<?xs.length>):>int64=>{xs.truncate(xs.length) return xs[i]}
main=():>int64=>{let xs:array<int64>=[42] return keep(@xs 0)}''',
]
ERRORS = [
    '''first=(@xs:array<int64> i:int64<v=>0<=?v<?xs.length> unused:int64):>int64=>xs[i]
clear=(@xs:array<int64>):>int64=>{xs.clear return 0}
main=():>int64=>{let xs:array<int64>=[42] return first(@xs 0 clear(@xs))}''',
    '''first=(@xs:array<int64> i:int64<v=>0<=?v<?xs.length> unused:int64):>int64=>xs[i]
change=(@xs:array<int64> @i:int64):>int64=>{xs.truncate(1) i=0 return 0}
main=():>int64=>{let xs:array<int64>=[1 42] let i:int64=1 return first(@xs i change(@xs @i))}''',
    '''cap=(@xs:array<int64> count:int64<v=>v>=?0>):>void & <xs.length=?count>=>{xs.truncate(count)}''',
    '''cap=(@xs:array<int64> count:int64<v=>0<=?v<=?xs.length>):>void & <xs.length=?count>=>{xs.truncate(count) count=0}''',
    '''cap=(@xs:array<int64> count:int64<v=>0<=?v<=?xs.length> i:int64<v=>0<=?v<?xs.length>):>int64=>{xs.truncate(count) return xs[i]}''',
    '''cap=(@xs:array<int64> count:int64<v=>0<=?v<=?xs.length>):>void & <xs.length=?count>=>{xs.truncate(count) xs.clear}''',
]

@pytest.mark.parametrize('source', CASES)
def test_truncate_relations(tmp_path, source):
    execute(tmp_path, 'truncate-relations', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_truncate_does_not_preserve_stale_facts(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_truncate_relations(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
