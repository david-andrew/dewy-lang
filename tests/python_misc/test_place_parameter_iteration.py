"""A loop over a place parameter or place-lent local borrows it when the loop body cannot write it.

Only this function's own writes and places can reach a place parameter that
no ambient alias names, so the loop body alone decides; calls that do not
take it as a place cannot change it."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

READ_ONLY = '''$explicit_copies
same=(a:int64 b:int64):>bool=>a =? b
add=(@pairs:array<int64> value:int64):>void=>{
    let found=false
    loop pair in pairs {if same(pair value) {found=true break}}
    if not found {pairs.push(value)}
}
main=():>int64=>{
    let xs:array<int64>=[]
    add(@xs 40) add(@xs 2) add(@xs 40)
    return if xs.length =? 2 xs[0]+xs[1] else 1
}
'''
# Writing the parameter inside the loop still iterates the entry value.
WRITING = '''grow=(@items:array<int64>):>int64=>{
    let seen:int64=0
    loop item in items {
        seen+=1
        items.push(item)
    }
    return seen
}
main=():>int64=>{
    let xs:array<int64>=[1 2 3]
    let seen=grow(@xs)
    return if seen =? 3 and xs.length =? 6 42 else 1
}
'''
# A local lent as a place before the loop is reached only through this
# function's own writes and places once the call returns.
LENT_LOCAL = '''$explicit_copies
fill=(@xs:array<int64>):>void=>{xs.push(40) xs.push(2)}
twice=(x:int64):>int64=>x*2
main=():>int64=>{
    let xs:array<int64>=[]
    fill(@xs)
    let total:int64=0
    loop x in xs {total+=twice(x)}
    return if total =? 84 42 else 1
}
'''
# Lending it again inside the loop still iterates the entry value.
RELENT_LOCAL = '''fill=(@xs:array<int64>):>void=>{xs.push(1)}
main=():>int64=>{
    let xs:array<int64>=[]
    fill(@xs) fill(@xs)
    let seen:int64=0
    loop x in xs {seen+=x fill(@xs)}
    return if seen =? 2 and xs.length =? 4 42 else 1
}
'''
CASES = [READ_ONLY, WRITING, LENT_LOCAL, RELENT_LOCAL]
ERRORS = ['$explicit_copies\n' + WRITING, '$explicit_copies\n' + RELENT_LOCAL]


@pytest.mark.parametrize('source', CASES)
def test_place_parameter_iteration(tmp_path, source):
    execute(tmp_path, 'place-iteration', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_written_place_parameter_keeps_its_snapshot(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_place_parameter_iteration(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
