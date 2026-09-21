"""Iterator inputs run once; predicates and body facts must survive backedges."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

CASES = [
    '''main=():>int64=>{let pending:array<int64>=[1]
let seen:set<int64>=set[] let children:dict<int64 set<int64>>=[1->set[42]]
let result:int64=0
loop pending.length>?0 {
    loop child in children.get(pending.pop set[]) {
        if child not in? seen {seen.add(child) pending.push(child) result=child}
    }
}
return result}''',
    '''main=():>int64=>{let pending:array<int64>=[42] let result:int64=0
loop pending.length>?0 {loop value in [pending.pop] {result=value pending.push(1) break} break}
return result}''',
    '''main=():>int64=>{let xs:array<int64>=[42] let result:int64=0
loop xs.length>?0 {result=xs.pop} return result}''',
]
ERRORS = [
    '''main=():>int64=>{let xs:array<int64>=[42]
loop i in [0..2) {xs.pop;} return 42}''',
    '''main=():>int64=>{let xs:array<int64>=[42]
loop i in [0..2) and xs.pop>?0 {xs.clear} return 42}''',
]


@pytest.mark.parametrize('source', CASES)
def test_iterator_entry_facts(source, tmp_path):
    execute(tmp_path, 'iterator-entry', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_iterator_backedge_forgets_consumed_storage(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_iterator_entry_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
