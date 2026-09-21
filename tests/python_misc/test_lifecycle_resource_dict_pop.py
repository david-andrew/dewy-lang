"""Removed dictionary entries no longer own logical resources."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/lifecycle_resource_dict_pop.dewy').read_text()
HANDLE = '''let drops:int64=0
Handle=type of [id:int64 $__drop__ release=():>void=>{drops+=id}]
'''
CASES = [SOURCE,
    HANDLE+'''work=():>int64=>{let d:dict<int64 Handle>=[1->Handle[10] 2->Handle[20]]
 let a=d.pop(1 default=Handle[5])
 if drops not=?5 or a.id not=?10 return 1
 let b=d.pop(3 default=Handle[30])
 if b.id not=?30 or drops not=?5 return 2
 return 42}
main=():>int64=>{if work() not=?42 or drops not=?65 return 1 return 42}''',
    HANDLE+'''work=():>int64=>{let d:dict<int64 array<Handle>>=[1->[Handle[10]] 2->[Handle[20]]]
 let a=d.pop(1) if a.length not=?1 return 1 return 42}
main=():>int64=>{if work() not=?42 or drops not=?30 return 1 return 42}''',
    HANDLE+'''work=():>int64=>{let d:dict<int64 Handle?>=[1->Handle[10] 2->none]
 let a=d.pop(1) let b=d.pop(2) if a is? none or b isnt? none return 1 return 42}
main=():>int64=>{if work() not=?42 or drops not=?10 return 1 return 42}''',
]
CASES += [SOURCE[:SOURCE.index('work=')]+'''work=(key:int64):>int64=>{
 let d:dict<int64 Handle>=[1->Handle[10 []] 2->Handle[20 []] 3->Handle[30 []]]
 d.pop(1);
 if key in? d {let saved=d.copy() if d[key].id not=?20 return 1 return 42}
 return 2}
main=():>int64=>{if work(2) not=?42 or drops not=?110 return 1 return 42}''']
ERRORS = [
    HANDLE+'''main=():>int64=>{let d:dict<int64 Handle>=[1->Handle[10]] let a=d.pop(1) let b=d.pop(1) return 42}''',
    HANDLE+'''reset=(@d:dict<int64 Handle>):>Handle=>{d.clear Handle[20]}
main=():>int64=>{let d:dict<int64 Handle>=[1->Handle[10]] let a=d.pop(1 default=reset(@d)) return 42}''',
    SOURCE.replace('work=():>int64=>','work=():>int64 & no_effects=>'),
]

@pytest.mark.parametrize('source', CASES)
def test_resource_dictionary_pop(tmp_path, source):
    execute(tmp_path, 'pop', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_resource_dictionary_pop_obligations(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_resource_dictionary_pop(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
