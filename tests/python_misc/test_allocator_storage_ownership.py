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


CASES.append(PREFIX + """Box:type=[text:string number:int64]
change=(@xs:array<Box> @arena:Arena):>void=>{
    let previous=_allocator_enter(@arena)
    if xs.length>?0 {xs[0].number=42}
    _allocator_exit(previous)
}
main=():>int64=>{
    let arena=Arena[]
    let xs:array<Box>=[Box[label(1) 1]]
    let before=xs.copy()
    change(@xs @arena)
    arena.reset()
    reuse(@arena)
    if xs.length not=?1 or before.length not=?1 return 1
    if xs[0].text not=?"item 1" or before[0].number not=?1 return 2
    return xs[0].number
}""")


CASES.append(PREFIX + """change=(@xs:array<int64?> @arena:Arena):>void=>{
    let previous=_allocator_enter(@arena)
    if xs.length>?0 {xs[0]=42}
    _allocator_exit(previous)
}
main=():>int64=>{
    let arena=Arena[]
    let xs:array<int64?>=[1 2]
    let before=xs.copy()
    change(@xs @arena)
    arena.reset()
    reuse(@arena)
    if xs.length not=?2 or before.length not=?2 return 1
    let untouched=xs[1]
    let original=before[0]
    let changed=xs[0]
    if untouched is?none or original is?none or changed is?none return 2
    return if untouched=?2 and original=?1 and changed=?42 42 else 3
}""")


CASES.append(PREFIX + """change=(@xs:array<string?> @arena:Arena):>void=>{
    let previous=_allocator_enter(@arena)
    if xs.length>?0 {xs[0]=label(42)}
    _allocator_exit(previous)
}
main=():>int64=>{
    let arena=Arena[]
    let xs:array<string?>=[label(1)]
    let before=xs.copy()
    change(@xs @arena)
    arena.reset()
    reuse(@arena)
    if xs.length not=?1 or before.length not=?1 return 1
    let changed=xs[0]
    let original=before[0]
    if changed is?none or original is?none return 2
    return if changed=?"item 42" and original=?"item 1" 42 else 3
}""")
CASES.append(PREFIX + """change=(@xs:array<(array<int64>)?> @arena:Arena):>void=>{
    let previous=_allocator_enter(@arena)
    if xs.length>?0 {xs[0]=build(42)}
    _allocator_exit(previous)
}
main=():>int64=>{
    let arena=Arena[]
    let xs:array<(array<int64>)?>=[build(1)]
    let before=xs.copy()
    change(@xs @arena)
    arena.reset()
    reuse(@arena)
    if xs.length not=?1 or before.length not=?1 return 1
    let changed=xs[0]
    let original=before[0]
    if changed is?none or original is?none return 2
    if changed.length not=?1 or original.length not=?1 return 3
    return if changed[0]=?42 and original[0]=?1 42 else 4
}""")


# Destination placement cannot move evaluation of the source into that context.
CASES.append(CASES[-2].replace('label=(n:int64):>string=>"item {n}"',
    """let observed:int64=0
label=(n:int64):>string=>{
    let pointer=_arena_alloc(8)
    observed=_allocator_of(pointer)
    _arena_release(pointer 8)
    return "item {n}"
}""").replace('    arena.reset()', '    if observed not=?arena.handle return 5\n    arena.reset()'))


# Promotion consumes the original owned cell, including its aggregate payload.
# Repeating the entire region/reset path must not retain heap references.
CASES.append(CASES[-2].replace('main=():>int64=>', 'exercise=():>int64=>') + """
main=():>int64=>{
    if exercise() not=?42 return 1
    let before=_arena_live_bytes
    loop i in [0..40) {if exercise() not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}
""")


CASES.append((Path(__file__).parents[1] / 'fixtures/allocator_storage_ownership.dewy').read_text())


@pytest.mark.parametrize('source', CASES)
def test_allocator_storage_owner(tmp_path, source):
    execute(tmp_path, 'allocator-owner', codegen(SrcFile(None, source), debug_locations=False))


def test_native_allocator_storage_owner(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
