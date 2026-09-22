"""Optional aggregate entries retain their stored presence bit in loop targets."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

CASES = [
    '''Box:type=[text:string value:int64]
main=():>int64=>{
    let entries:dict<string Box?>=['empty'->none 'full'->Box['ok' 42] 'last'->none]
    let total:int64=0 let absent:int64=0
    loop [key box] in entries {
        if box is? none {absent+=1 continue}
        if box.text not=?'ok' return 1
        total+=box.value
    }
    return if absent=?2 total else 2
}''',
    '''Box:type=[items:array<int64>]
main=():>int64=>{
    let entries:dict<string Box?>=['empty'->none 'full'->Box[[20 22]]]
    let total:int64=0
    loop [key values] in entries {
        if values is? none continue
        loop value in values.items {total+=value}
    }
    return total
}''',
    '''Box:type=[value:int64]
main=():>int64=>{
    let values:array<Box?>=[none Box[20] Box[22]]
    let sum:int64=0 let absent:int64=0
    loop value in values or index in [0..5) {
        if value is? none {absent+=1 continue}
        sum+=value.value
    }
    return if absent=?3 sum else 1
}''',
]

@pytest.mark.parametrize('source', CASES)
def test_optional_aggregate_iteration(source, tmp_path):
    execute(tmp_path, 'optional-aggregate-iteration', codegen(SrcFile(None, source)))


def test_native_optional_aggregate_iteration(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
