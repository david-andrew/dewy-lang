"""Loop exits contained in an allocator block preserve its fallthrough exit."""
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


def test_hosted_allocator_nonlocal_exit_retains_fallback():
    src = SrcFile(None, '''main=():>int64=>{
        let arena=Arena[]
        loop i in [0..2) {$allocator(@arena) {if i=?1 break}}
        return 42
    }''')
    codegen(src, debug_locations=False)
    assert any('control-flow exits' in note.reason for note in lower.last_placement_notes if note.srcfile == src)


def test_native_allocator_local_exits(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
