"""A field taken from a dying owner moves, and a field stored back renews it.

A store to a fixed field path means a later whole read of the owner reads the
new value there: before the store, only the sibling fields stay live. A plain,
optional or narrowed optional field taken out and stored back is therefore a
move. A read of the old value in between still keeps the copy."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''State:type = [values:array<int64>]
Output:type = [normal:State?=none count:int64=0]
Plain:type = [normal:State count:int64=0]
values=(n:int64):>array<int64>=>{
    let result:array<int64>=[]
    let i:int64=0
    loop i <? n {result.push(i) i+=1}
    return result
}
'''
MOVED = '$explicit_copies\n' + PRELUDE + '''plain=(n:int64):>Plain=>{
    let result=Plain[State[values(n)] n]
    let remaining=result.normal
    remaining.values.push(9)
    result.normal=remaining
    return result
}
optional=(n:int64):>Output=>{
    let result=Output[State[values(n)] n]
    let remaining=result.normal
    if remaining isnt? none {remaining.values.push(9)}
    result.normal=remaining
    return result
}
narrowed=(n:int64):>Output=>{
    let result=Output[State[values(n)] n]
    if result.normal isnt? none {
        let remaining=result.normal
        remaining.values.push(9)
        result.normal=remaining
    }
    return result
}
collect=(n:int64):>int64=>{
    let exits:array<State>=[]
    let bound=Output[State[values(n)] n]
    if bound.normal isnt? none {exits.push(bound.normal)}
    let total:int64=bound.count
    loop exit in exits {total+=exit.values.length}
    return total
}
main=():>int64=>{
    let p=plain(3)
    let o=optional(3)
    let r=narrowed(3)
    let o_length=if o.normal is? none 0 else o.normal.values.length
    let r_length=if r.normal is? none 0 else r.normal.values.length
    let ok=p.normal.values.length =? 4 and o_length =? 4 and r_length =? 4 and collect(5) =? 10
    return if ok 42 else 1
}
'''
# Reading the owner between the take and the store needs the old value.
OBSERVED = PRELUDE + '''observed=(n:int64):>int64=>{
    let result=Plain[State[values(n)] n]
    let remaining=result.normal
    remaining.values.push(9)
    let before=result.normal.values.length
    result.normal=remaining
    return before*10+result.normal.values.length
}
main=():>int64=>if observed(3) =? 34 42 else 1
'''
CASES = [MOVED, OBSERVED]
ERRORS = ['$explicit_copies\n' + OBSERVED]


@pytest.mark.parametrize('source', CASES)
def test_field_take_and_renew(tmp_path, source):
    execute(tmp_path, 'field-renew', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_observed_old_field_keeps_its_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_field_take_and_renew(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
