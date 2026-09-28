"""Storage copies/growth respect allocator ownership, including nested arrays."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

PREFIX = '''build=(n:int64):>array<int64>=>{let xs:array<int64>=[] xs.push(n) return xs}
label=(n:int64):>string=>"item {n}"
reuse=(@arena:Arena):>void=>{
    let previous=_allocator_enter(@arena)
    let junk=build(99)
    let text=label(99)
    _allocator_exit(previous)
}
'''
CASES = [PREFIX + '''snapshot=(@arena:Arena):>array<int64>=>{
    let previous=_allocator_enter(@arena)
    let xs=build(42)
    _allocator_exit(previous)
    return xs.copy()
}
main=():>int64=>{
    let arena=Arena[]
    let xs=snapshot(@arena)
    arena.reset()
    reuse(@arena)
    return if xs.length=?1 xs[0] else 1
}''', PREFIX + '''snapshot=(@arena:Arena):>string=>{
    let previous=_allocator_enter(@arena)
    let text=label(42)
    _allocator_exit(previous)
    return text.copy()
}
main=():>int64=>{
    let arena=Arena[]
    let text=snapshot(@arena)
    arena.reset()
    reuse(@arena)
    return if text=?"item 42" 42 else 1
}''', PREFIX + '''grow=(@xs:array<int64> @arena:Arena):>void=>{
    let previous=_allocator_enter(@arena)
    loop i in [0..20) {xs.push(42)}
    _allocator_exit(previous)
}
main=():>int64=>{
    let arena=Arena[]
    let xs=build(1)
    grow(@xs @arena)
    arena.reset()
    reuse(@arena)
    if xs.length not=?21 return 1
    loop i in [1..xs.length) {if xs[i] not=?42 return 2}
    return 42
}''', PREFIX + '''change=(@xs:array<array<int64>> @arena:Arena):>void=>{
    let previous=_allocator_enter(@arena)
    if xs.length>?0 and xs[0].length>?0 {xs[0][0]=42}
    _allocator_exit(previous)
}
main=():>int64=>{
    let arena=Arena[]
    let xs:array<array<int64>>=[build(1)]
    let before=xs.copy()
    change(@xs @arena)
    arena.reset()
    reuse(@arena)
    if xs.length not=?1 or xs[0].length not=?1 return 1
    if before.length not=?1 or before[0].length not=?1 or before[0][0] not=?1 return 2
    return xs[0][0]
}''']


CASES.append((Path(__file__).parents[1] / 'fixtures/allocator_storage_ownership.dewy').read_text())


@pytest.mark.parametrize('source', CASES)
def test_allocator_storage_owner(tmp_path, source):
    execute(tmp_path, 'allocator-owner', codegen(SrcFile(None, source), debug_locations=False))


def test_native_allocator_storage_owner(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
