"""Dictionary live counts are separate from tombstone-bearing array lengths."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

CASES = [
    'let calls:int64=0\nselect=():>0=>{calls+=1 0}\nmain=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]] let snapshot=groups groups[select()].clear return if calls=?1 and groups[0].length=?0 and snapshot[0].length=?1 42 else 1}', 
    'main=():>int64=>{let d:dict<int64 int64>=[1->2 2->3] d.pop(1); d.clear $assert d.length=?0 return 42}',
    'main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]] groups[0].clear $assert groups[0].length=?0 return 42}',
    'main=():>int64=>{let s:set<int64>=set[1 2] s.clear $assert s.length=?0 return 42}',
]
ERRORS = [
    'work=(i:int64<v=>0<=?v<?2>):>int64=>{let groups:array<dict<int64 int64>>=[[1->2] [1->2]] groups[0].clear groups[i][2]=3 $assert groups[0].length=?0 return 42}\nmain=():>int64=>work(0)', 
    'main=():>int64=>{let groups:array<dict<int64 int64>>=[[1->2]] groups[0].clear let i:int64=0 groups[i][2]=3 $assert groups[0].length=?0 return 42}',
    'main=():>int64=>{const groups:array<dict<int64 int64>>=[[1->2]] groups[0].clear return 42}',
    'main=():>int64=>{let box:[const groups:array<dict<int64 int64>>]=[[[1->2]]] box.groups[0].clear return 42}', 
    'main=():>int64=>{let d:dict<int64 int64>=[1->2] d.clear d[2]=3 $assert d.length=?0 return 42}',
    'main=():>int64=>{let d:dict<int64 int64>=[1->2] if d.length=?1 {d.pop(1); $assert d.length=?1} return 42}',
    'main=():>int64=>{let d:dict<int64 int64>=[1->2] if d.length=?1 {d[2]=3 $assert d.length=?1} return 42}',
    'main=():>int64=>{let s:set<int64>=set[1 2] s.clear s.push(3) $assert s.length=?0 return 42}',
]


@pytest.mark.parametrize('source', CASES)
def test_dictionary_empty_fact(tmp_path, source):
    execute(tmp_path, 'dict-length', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_dictionary_mutations_forget_old_counts(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_dictionary_length_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
