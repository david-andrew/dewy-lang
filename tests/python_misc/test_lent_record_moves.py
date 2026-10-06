"""A record local lent as a place moves after its last loan.

`facts.put(@current …)` lends `current`'s own block; no place argument
outlives its call, so the final `result.state=current` takes the handle.
A read inside a call that also lends the local, or that shares a call's
arguments with another read of it, stays in place. A local that
is assigned whole is written in place through its block in native code, so
it keeps its block (and copies at the store) rather than moving.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

PRELUDE = '''State:type=[values:array<int64>]
Holder:type=[state:State?]
put=(@state:State n:int64):>void=>{state.values.push(n)}
'''
MOVED = '$explicit_copies\n' + PRELUDE + '''build=(n:int64):>Holder=>{
    let current=State[[]]
    let i:int64=0
    loop i <? n {put(@current i) i+=1}
    let result=Holder[none]
    result.state=current
    return result
}
main=():>int64=>{
    let before:int64=_arena_live_bytes
    let total:int64=0
    let k:int64=0
    loop k <? 50 {
        let h=build(3)
        if h.state isnt? none {total+=h.state.values.length}
        k+=1
    }
    return if total=?150 and _arena_live_bytes=?before 42 else 1
}
'''
# Assigned whole after the store: the stored value must stay independent.
REBOUND = PRELUDE + '''main=():>int64=>{
    let holders:array<Holder>=[]
    let current=State[[]]
    let k:int64=0
    loop k <? 3 {
        put(@current k)
        holders.push(Holder[none])
        let last=holders.length-1
        if last >=? 0 and last <? holders.length {holders[last].state=current}
        current=State[[]]
        k+=1
    }
    let total:int64=0
    loop holder in holders {if holder.state isnt? none {total+=holder.state.values.length}}
    return total+39
}
'''
# An earlier argument still borrows `current` while a later one would take it.
SHARED = PRELUDE + '''measure=(s:State h:Holder):>int64=>s.values.length+(if h.state isnt? none h.state.values.length else 0)
wrap=(s:State):>Holder=>Holder[s]
main=():>int64=>{
    let current=State[[]]
    put(@current 1)
    return measure(current wrap(current))+40
}
'''
CASES = [MOVED, REBOUND, SHARED]


@pytest.mark.parametrize('source', CASES)
def test_lent_record_moves(tmp_path, source):
    execute(tmp_path, 'lent-record', codegen(SrcFile(None, source), debug_locations=False))


def test_native_lent_record_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
