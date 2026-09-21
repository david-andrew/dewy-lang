"""Implicit dictionary places survive selection and argument evaluation."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''let calls:int64=0
select=(@groups:array<dict<int64 int64>>):>0=>{calls+=1 return 0}
main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]] let saved=groups
 groups[select(@groups)][2]=40
 if calls not=?1 or saved[0].length not=?1 return 1
 if 2 in? groups[0] {return groups[0][2]+2}
 return 1}''',
    '''read=(groups:array<dict<int64 int64>> i:int64):>int64=>{
 if 0<=?i and i<?groups.length {return groups[i].get(1 default=0)}
 return 0}
main=():>int64=>read([[1->42]] 0)''',
    '''select=(@groups:array<dict<int64 int64>>):>0=>0
main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]]
 groups[select(@groups)].clear
 return if groups[0].length=?0 42 else 1}''',
]
RESET = 'reset=(@groups:array<dict<int64 int64>>):>0=>{groups.clear return 0}\n'
ERRORS = [
    RESET+'main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]] groups[reset(@groups)].clear return 42}',
    RESET+'main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]] groups[0][reset(@groups)]=3 return 42}',
    RESET+'main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]] groups[0][2]=reset(@groups) return 42}',
    RESET+'main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]] groups[0].pop(1 default=reset(@groups)); return 42}',
    '''main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]]
 reset=():>int64=>{groups.clear return 0}
 groups[0][2]=reset() return 42}''',
    '''let groups:array<dict<int64 int64>>=[[1->2]]
reset=():>int64=>{groups.clear return 0}
main=():>int64=>{groups[0][2]=reset() return 42}''',
    'clear=(groups:array<dict<int64 int64>> i:int64):>void=>{groups[i].clear}\nmain=():>int64=>{clear([] 0) return 42}',
    'read=(groups:array<dict<int64 int64>> i:int64):>int64?=>groups[i].get(1)\nmain=():>int64=>{read([] 0); return 42}',
]


@pytest.mark.parametrize('source', CASES)
def test_container_receiver_evaluated_once(tmp_path, source):
    execute(tmp_path, 'receiver', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_container_receiver_must_survive(source):
    with pytest.raises(ReportException, match='receiver changes|index.*bounds'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_container_receiver_lifetimes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
