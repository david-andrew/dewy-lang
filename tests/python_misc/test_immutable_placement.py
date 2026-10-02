"""Storage an immutable record holds, placed into an immutable record, is shared.

Immutability is deep, so no holder of either record can ever write that
storage: the copy is a bounded share. A writable source or destination still
needs a real copy."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SHARED = '''$explicit_copies
Row:type = const [atoms:array<int64>=[] variables:array<string>=[] unknown:bool=false]
Contract:type = const [allowed:Row excluded:array<int64>=[]]
add=(row:Row atom:int64):>Row=>{
    let remaining:array<int64>=[]
    loop old in row.atoms {if old not=? atom {remaining.push(old)}}
    remaining.push(atom)
    return Row[remaining row.variables row.unknown]
}
widen=(contract:Contract):>Contract=>Contract[Row[contract.allowed.atoms unknown=true] contract.excluded]
main=():>int64=>{
    let r=add(Row[[1 2] ['x']] 3)
    let c=widen(Contract[r [7]])
    let ok=r.atoms.length =? 3 and r.variables.length =? 1 and c.allowed.atoms.length =? 3 and c.excluded.length =? 1
    return if ok 42 else 1
}
'''
# A writable destination owns storage its holder may change.
WRITABLE_DESTINATION = '''Row:type = const [variables:array<string>]
Box:type = [variables:array<string>]
names=(count:int64):>array<string>=>{
    let result:array<string>=[]
    let i:int64=0
    loop i <? count {result.push('x') i+=1}
    return result
}
main=():>int64=>{
    let row=Row[names(1)]
    let box=Box[row.variables]
    box.variables.push('y')
    return if row.variables.length =? 1 and box.variables.length =? 2 42 else 1
}
'''
# A writable source may still change after the placement.
WRITABLE_SOURCE = '''Row:type = const [variables:array<string>]
Box:type = [variables:array<string>]
names=(count:int64):>array<string>=>{
    let result:array<string>=[]
    let i:int64=0
    loop i <? count {result.push('x') i+=1}
    return result
}
main=():>int64=>{
    let box=Box[names(1)]
    let row=Row[box.variables]
    box.variables.push('y')
    return if row.variables.length =? 1 and box.variables.length =? 2 42 else 1
}
'''
CASES = [SHARED, WRITABLE_DESTINATION, WRITABLE_SOURCE]
ERRORS = ['$explicit_copies\n' + WRITABLE_DESTINATION, '$explicit_copies\n' + WRITABLE_SOURCE]


@pytest.mark.parametrize('source', CASES)
def test_immutable_placement(tmp_path, source):
    execute(tmp_path, 'immutable-placement', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_writable_placement_stays_reported(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_immutable_placement(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
