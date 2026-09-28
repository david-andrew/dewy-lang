"""Loop exits contained in an allocator block preserve its fallthrough exit."""
import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SOURCE = '''build=(n:int64):>array<int64>=>{
    let xs:array<int64>=[]
    loop i in [0..n) {xs.push(i)}
    return xs
}
main=():>int64=>{
    let arena=Arena[]
    let size=$allocator(@arena) {
        let xs:array<int64>=[]
        loop i in [0..10) {
            if i=?1 continue
            xs.push(build(i).length)
            if i=?4 break
        }
        xs.length
    }
    if size not=?4 or arena.handle=?0 return 1
    let check=_arena_alloc(8)
    let owner=_allocator_of(check)
    _arena_release(check 8)
    return if owner=?0 42 else 2
}'''


def test_hosted_allocator_local_exits(tmp_path):
    src = SrcFile(None, SOURCE)
    emitted = codegen(src, debug_locations=False)
    assert not [note for note in lower.last_placement_notes if note.srcfile == src]
    execute(tmp_path, 'allocator-local-exits', emitted)




def test_native_allocator_local_exits(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])


EXIT_PREFIX = """build=(n:int64):>array<int64>=>{let xs:array<int64>=[] xs.push(n) return xs}
heap_owner=():>int64=>{
    let pointer=_arena_alloc(8)
    let owner=_allocator_of(pointer)
    _arena_release(pointer 8)
    return owner
}
"""
EXIT_CASES = [EXIT_PREFIX + """work=(@arena:Arena):>int64=>{
    $allocator(@arena) {let xs=build(42) if xs.length>?0 return xs[0]}
    return 0
}
main=():>int64=>{let arena=Arena[] let value=work(@arena)
    return if value=?42 and arena.handle not=?0 and heap_owner()=?0 42 else 1}
""", EXIT_PREFIX + """main=():>int64=>{
    let arena=Arena[]
    let total:int64=0
    loop i in [0..5) {
        $allocator(@arena) {
            let xs=build(i)
            if i=?1 continue
            if i=?3 break
            total+=xs.length
        }
    }
    return if total=?2 and arena.handle not=?0 and heap_owner()=?0 42 else 1
}
""", EXIT_PREFIX + """work=(@outer:Arena @inner:Arena):>int64=>{
    $allocator(@outer) {$allocator(@inner) {let xs=build(42) if xs.length>?0 return xs[0]}}
    return 0
}
main=():>int64=>{let outer=Arena[] let inner=Arena[] let value=work(@outer @inner)
    return if value=?42 and outer.handle not=?0 and inner.handle not=?0 and heap_owner()=?0 42 else 1}
""", EXIT_PREFIX + """let observed:int64=0
Handle=type of [id:int64
    $__drop__
    release=():>void=>{observed=heap_owner()}
]
work=(@arena:Arena):>int64=>{
    $allocator(@arena) {let value=Handle[42] return value.id}
}
main=():>int64=>{
    let arena=Arena[]
    let value=work(@arena)
    return if value=?42 and observed=?arena.handle and observed not=?0 and heap_owner()=?0 42 else 1
}
"""]


EXIT_CASES.extend([EXIT_PREFIX + """main=():>int64=>{
    let arena=Arena[]
    let total:int64=0
    $outer
    loop i in [0..5) {
        $allocator(@arena) {
            let xs=build(i)
            loop true {total+=xs.length break $outer}
        }
    }
    return if total=?1 and arena.handle not=?0 and heap_owner()=?0 42 else 1
}
"""])

@pytest.mark.parametrize('source', EXIT_CASES)
def test_hosted_allocator_outward_exits(tmp_path, source):
    src=SrcFile(None, source)
    emitted=codegen(src, debug_locations=False)
    assert not [note for note in lower.last_placement_notes if note.srcfile==src]
    execute(tmp_path, 'allocator-outward-exits', emitted)


def test_native_allocator_outward_exits(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=EXIT_CASES, errors=[])
