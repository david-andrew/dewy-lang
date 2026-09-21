"""Logical ownership of dictionary reads, insertions and replacements."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/lifecycle_resource_dict_entries.dewy').read_text()
HANDLE = '''let drops:int64=0
let copies:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{drops+=id}
$__copy__
clone=():>Handle=>{copies+=1 Handle[id]}
]
'''
CASES = [SOURCE,
    HANDLE+'''work=():>int64=>{let d:dict<int64 array<Handle>>=[1->[Handle[10]]]
 let h=d[1] d[1]=[Handle[20]] d[2]=[Handle[30]]
 if copies not=?1 or drops not=?10 or h.length not=?1 return 1
 return 42}
main=():>int64=>{if work() not=?42 or drops not=?70 return 1 return 42}''',
    HANDLE+'''work=():>int64=>{let d:dict<int64 Handle?>=[1->Handle[10] 2->none]
 let h=d[1] d[1]=none d[2]=Handle[20]
 if copies not=?1 or drops not=?10 or h is? none return 1
 return 42}
main=():>int64=>{if work() not=?42 or drops not=?40 return 1 return 42}''',
    '''let drops:int64=0
Handle=type of [id:int64 $__drop__ release=():>void=>{drops+=id}]
work=():>int64=>{let d:dict<int64 Handle>=[] let h=Handle[10]
 d[1]=h d[1]=Handle[20] d[2]=Handle[30] return 42}
main=():>int64=>{if work() not=?42 or drops not=?60 return 1 return 42}''',
]
CASES += [CASES[1].replace('let h=d[1]', 'let h=d[1].copy()'),
    CASES[3].replace('d[1]=h d[1]=Handle[20]', 'if drops=?0 {d[1]=h} else {d[1]=Handle[10]} d[1]=Handle[20]')]
CASES += [(ROOT / 'tests/fixtures/lifecycle_resource_dict_get.dewy').read_text()]
ERRORS = [
    CASES[3].replace('d[1]=h d[1]', 'd[1]=h if h.id=?10 return 1 d[1]'),
    HANDLE+'''reset=(@d:dict<int64 Handle>):>Handle=>{d.clear Handle[20]}
main=():>int64=>{let d:dict<int64 Handle>=[1->Handle[10]]
 d[1]=reset(@d) return 42}''',
    SOURCE.replace('work=():>int64=>', 'work=():>int64 & no_effects=>'),
]

@pytest.mark.parametrize('source', CASES)
def test_resource_dictionary_entries(tmp_path, source):
    execute(tmp_path, 'entries', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_resource_dictionary_entry_obligations(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_resource_dictionary_entries(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
