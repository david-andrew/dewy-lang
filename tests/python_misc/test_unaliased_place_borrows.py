"""A place no caller fills with a global is not reached by ambient writes.

A callee that writes module state (here, clearing a log array) cannot change
storage a place parameter refers to unless some caller passes a global as
that place (`global_placed`). Native borrowing now lends such a place's
fields to read-only callees instead of copying them; a function whose place
may hold a global keeps the copy. The hosted storage proof still excludes
every parameter of a function an ambient write blocks, so `LOCAL` runs
without checking copies here; the strict `validation` module relies on the
native rule in every self-build.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

PRELUDE = '''Box:type=[items:array<int64>]
let log:array<int64>=[]
note=():>void=>{log.clear()}
measure=(items:array<int64>):>int64=>{
    note()
    return items.length
}
'''
LOCAL = PRELUDE + '''holder=(@box:Box):>int64=>measure(box.items)
main=():>int64=>{
    let b=Box[[1 2]]
    note()
    let before:int64=_arena_live_bytes
    let total:int64=0
    let k:int64=0
    loop k <? 20 {total+=holder(@b) k+=1}
    return if total=?40 and _arena_live_bytes=?before 42 else 1
}
'''
GLOBAL = PRELUDE + '''let shared=Box[[1 2 3]]
holder=(@box:Box):>int64=>measure(box.items)
main=():>int64=>holder(@shared)+39
'''
CASES = [LOCAL, GLOBAL]
ERRORS = ['$explicit_copies\n' + GLOBAL]


@pytest.mark.parametrize('source', CASES)
def test_unaliased_place_borrows(tmp_path, source):
    execute(tmp_path, 'unaliased-place', codegen(SrcFile(None, source), debug_locations=False))


def test_native_unaliased_place_borrows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
