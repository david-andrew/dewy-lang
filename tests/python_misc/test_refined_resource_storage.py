"""Checked refinements do not change the resource's ownership layout."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HANDLE = '''let drops:int64=0
Handle=type of [id:int64 $__drop__ release=():>void=>{drops+=id}]
'''
CASES = [
    HANDLE+'''work=():>int64=>{let d:totaldict<'a'|'b' Handle>=['a'->Handle[1] 'b'->Handle[2]]
d['a']=Handle[3] return if drops=?1 42 else 0}
main=():>int64=>{let result=work() return if drops=?6 result else 0}''',
    HANDLE+'''let selections:int64=0
key=():>'a'=>{selections+=1 return 'a'}
work=():>int64=>{let d:totaldict<'a' dict<int64 Handle>>=['a'->[1->Handle[1] 2->Handle[2]]]
d[key()].clear return if selections=?1 and drops=?3 42 else 0}
main=():>int64=>{let result=work() return if drops=?3 result else 0}''',
    HANDLE+'''work=():>int64=>{let h:Handle<id>=?0>=Handle[42] return h.id}
main=():>int64=>{let result=work() return if drops=?42 result else 0}''',
]
ERRORS = [
    HANDLE+'''work=():>int64=>{let d:totaldict<'a'|'b' Handle>=['a'->Handle[1]] return 42}''',
    HANDLE+'''work=():>int64=>{let h:Handle<id>=?0>=Handle[-1] return 42}''',
    CASES[0].replace("d['a']=Handle[3]", "d.clear"),
    CASES[0].replace('work=():>int64=>', 'work=():>int64 & no_effects=>'),
]

@pytest.mark.parametrize('source', CASES)
def test_refined_resource_storage(tmp_path, source):
    execute(tmp_path, 'refined-resource', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_refined_resource_contracts(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_refined_resource_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
