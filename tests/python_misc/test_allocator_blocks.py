"""`$allocator(@arena) { ... }`: accepted forms, escapes reported as copies, and rejections."""
import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.errors import TypeCheckError, UserError
from tests.python_misc.test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/allocator_blocks.dewy'
ARENA_FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/arena_blocks.dewy'
ARENA_OUTPUT = '100 item 7 6 50000 item 5/1 item 0 item 19 36 290 18,2,10 1,2 11 1\n'
# Placement is not observable through values, only through the arena's
# handle: native lowering gives a block that writes nothing outside it its
# arena, and allocates other blocks from the enclosing context.
PLACEMENT = '''build=(n:int64):>array<int64>=>{let xs:array<int64>=[] loop i in 0.. and i <? n and i <? 1000000 {xs.push(i + i)} return xs}
main=():>int64=>{
    let pure=Arena[]
    let xs=$allocator(@pure) {build(4)}
    let writer=Arena[]
    let kept:array<int64>=[]
    $allocator(@writer) {kept=build(3)}
    if pure.handle =? 0 or writer.handle not=? 0 return 1
    let outer=Arena[]
    let inner=Arena[]
    let n=$allocator(@outer) {
        let ys=$allocator(@inner) {build(2)}
        ys.length
    }
    if outer.handle =? 0 or inner.handle =? 0 return 2
    # A scalar store into outer storage does not keep a block off its arena.
    let counter=Arena[]
    let counts:array<int64>=[1]
    let shared=counts
    $allocator(@counter) {counts.push(build(5).length)}
    if counter.handle =? 0 or counts.length not=? 2 or shared.length not=? 1 return 3
    return 42+xs.length-4+kept.length-3+n-2
}'''

ERRORS = [
    # The arena is lent to its block.
    'main=():>int64=>{let a=Arena[] $allocator(@a) {a.reset()} return 0}',
    # Allocating mutates the arena: a place, not a value.
    'main=():>int64=>{let a=Arena[] $allocator(a) {1} return 0}',
    'main=():>int64=>{let n:int64=0 $allocator(@n) {1} return 0}',
    # Under `$explicit_copies`, a runtime-sized escape needs `.copy()`.
    '$explicit_copies\nbuild=(n:int64):>array<int64>=>{let xs:array<int64>=[] loop i in 0.. and i <? n {xs.push(i)} return xs}\n'
    'main=():>int64=>{let a=Arena[] let xs=$allocator(@a) {build(2)} return xs.length}',
]
# The directive needs its block.
PARSE_ERRORS = ['main=():>int64=>{let a=Arena[] $allocator(@a) return 0}']
STRICT = ('$explicit_copies\nbuild=(n:int64):>array<int64>=>{let xs:array<int64>=[] loop i in 0.. and i <? n {xs.push(i)} return xs}\n'
          'main=():>int64=>{let a=Arena[] let n=$allocator(@a) {build(40).length} let xs=$allocator(@a) {build(2).copy()} return n+xs.length}')


def test_allocator_blocks(tmp_path):
    source = SrcFile.from_path(FIXTURE)
    code = codegen(source, debug_locations=False)
    sites = [note.site for note in lower.last_copy_notes if note.srcfile.path == source.path
             and 'leave the `$allocator(@scratch)` block' in note.message]
    assert sites == ['produced as the block result', 'stored into `kept`'], sites
    execute(tmp_path, 'allocator-blocks', code)
    execute(tmp_path, 'allocator-strict', codegen(SrcFile(None, STRICT)))
    execute(tmp_path, 'arena-blocks', codegen(SrcFile.from_path(ARENA_FIXTURE)))


@pytest.mark.parametrize('source', ERRORS + PARSE_ERRORS)
def test_allocator_block_rejections(source):
    with pytest.raises((TypeCheckError, UserError, ReportException)):
        codegen(SrcFile(None, source))


def test_native_allocator_blocks(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[FIXTURE.read_text(), STRICT], errors=ERRORS)


def test_native_arena_blocks(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[ARENA_FIXTURE.read_text()], errors=[], outputs=[ARENA_OUTPUT])


def compile_native(tmp_path, name, text):
    import test_bootstrap_lowering as native_lowering
    from test_bootstrap_structural_text import build_program_driver
    source = tmp_path / f'{name}.dewy'
    source.write_text(text)
    return subprocess.run([build_program_driver(tmp_path), source, native_lowering.ROOT / 'library', tmp_path / 'prelude'],
                          capture_output=True, text=True, timeout=120)


def test_native_allocator_parse_errors(tmp_path):
    for index, text in enumerate(PARSE_ERRORS):
        result = compile_native(tmp_path, f'parse-error-{index}', text)
        assert result.returncode == 1 and 'Error' in result.stderr, (text, result.returncode, result.stderr)


def test_native_arena_placement(tmp_path):
    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point
    compiled = compile_native(tmp_path, 'placement', PLACEMENT)
    assert compiled.returncode == 0, compiled.stderr
    output = tmp_path / 'placement.udewy'
    output.write_text(compiled.stdout)
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        assert subprocess.run([cache_artifact(output).resolve()], timeout=10).returncode == 42, target
