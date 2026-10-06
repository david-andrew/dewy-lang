"""A read-only defaulted array parameter borrows a supplied argument.

As for a read-only record, an explicitly supplied array is the caller's
storage for the call; only the omitted default belongs to the callee, which
releases it on that path alone.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
count=(xs:array<int64> prefix:array<int64>=[]):>int64=>{
    let t:int64=xs.length
    loop p in prefix {t+=p}
    return t
}
main=():>int64=>{
    let before:int64=_arena_live_bytes
    let ys:array<int64>=[10 20]
    let total:int64=0
    let k:int64=0
    loop k <? 100 {
        total+=count(ys)+count(ys prefix=ys)
        k+=1
    }
    return if total=?3400 and ys.length=?2 and _arena_live_bytes=?before 42 else 1
}
'''
CASES = [SOURCE]


@pytest.mark.parametrize('source', CASES)
def test_defaulted_array_borrows(tmp_path, source):
    execute(tmp_path, 'defaulted-array', codegen(SrcFile(None, source), debug_locations=False))


def test_native_defaulted_array_borrows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
