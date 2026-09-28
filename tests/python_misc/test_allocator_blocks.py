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
# The directive needs a following expression.
PARSE_ERRORS = ['main=():>int64=>{let a=Arena[] $allocator(@a)}']
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


EXPRESSIONS = """build=(n:int64):>array<int64>=>{let xs:array<int64>=[] loop i in 0.. and i <? n {xs.push(i)} return xs}
main=():>int64=>{
    let a=Arena[]
    let b=Arena[]
    let n=if true $allocator(@a) build(18).length + build(20).length else 0
    let result=$allocator(@a) $allocator(@b) build(4)
    a.reset()
    b.reset()
    return n + result.length
}
"""


def test_allocator_expression_scope(tmp_path):
    execute(tmp_path, 'allocator-expressions', codegen(SrcFile(None, EXPRESSIONS)))


def test_hosted_allocator_fallback_report(capsys):
    from dewy.__main__ import analyze
    assert analyze(['--brief', str(FIXTURE)]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith('allocator: ')]
    assert len(lines) == 1
    assert 'aggregate copy-out' in lines[0] and str(FIXTURE) in lines[0]


def test_allocator_result_before_trailing_statements_is_reported():
    source = SrcFile(None, """make=(text:string):>string=>text
main=():>int64=>{
    let a=Arena[]
    let result=$allocator(@a) {
        let count=0
        make('hello')
        count=1
    }
    return 42
}
""")
    codegen(source)
    notes = [note for note in lower.last_copy_notes if note.srcfile == source
             and note.site == 'produced as the block result']
    assert len(notes) == 1 and notes[0].runtime_sized and not notes[0].policy_exempt
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n' + source.body))


def test_native_allocator_expressions(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[EXPRESSIONS], errors=[])


def test_native_allocator_fallback_report(tmp_path):
    import os
    import test_bootstrap_lowering as native_lowering
    from test_bootstrap_structural_text import build_program_driver
    source = tmp_path / 'placement.dewy'
    source.write_text(PLACEMENT)
    result = subprocess.run([build_program_driver(tmp_path), source, native_lowering.ROOT / 'library', tmp_path / 'prelude'],
                            env={**os.environ, 'DEWY_TEST_ALLOCATOR_NOTES': '1'},
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    notes = result.stdout.splitlines()
    assert len(notes) == 1 and '`kept`' in notes[0] and 'outside the block' in notes[0], notes


NO_ALLOCATION = Path(__file__).resolve().parents[1] / 'fixtures/allocator_no_allocation.dewy'


def test_allocator_no_allocation_warning(tmp_path, capsys):
    code = codegen(SrcFile.from_path(NO_ALLOCATION))
    warnings = capsys.readouterr().err
    assert warnings.count('allocator scope does not allocate') == 1, warnings
    assert str(NO_ALLOCATION) in warnings
    execute(tmp_path, 'allocator-no-allocation', code)


@pytest.mark.parametrize('source', [
    # A copied array has a logical storage obligation even if COW defers it.
    'f=(xs:array<int64>):>int64=>{let a=Arena[] return $allocator(@a) xs.copy().length}',
    # An omitted callback row is unknown, not a promise of no allocation.
    'f=(callback:():>int64):>int64=>{let a=Arena[] return $allocator(@a) callback()}',
    # Aggregate results owe copy-out storage even when their source is static.
    'f=():>string=>{let a=Arena[] return $allocator(@a) "hello"}',
])
def test_allocator_unknown_or_logical_allocation_does_not_warn(source, capsys):
    codegen(SrcFile(None, source))
    assert 'allocator scope does not allocate' not in capsys.readouterr().err


def test_allocator_invalid_contract_is_not_warning_evidence(capsys):
    source = '''bad=(xs:array<int64>):>array<int64> & no allocates=>xs.copy()
f=(xs:array<int64>):>int64=>{let a=Arena[] return $allocator(@a) bad(xs).length}
'''
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))
    assert 'allocator scope does not allocate' not in capsys.readouterr().err


def test_native_allocator_no_allocation_warning(tmp_path):
    # Reusing the checked prelude must not lose or duplicate source warnings.
    for _ in range(2):
        compiled = compile_native(tmp_path, 'allocator-no-allocation', NO_ALLOCATION.read_text())
        assert compiled.returncode == 0, compiled.stderr
        assert compiled.stderr.count('allocator scope does not allocate') == 1, compiled.stderr


SCALAR_PLACEMENT = Path(__file__).resolve().parents[1] / 'fixtures/scalar_allocator_placement.dewy'


def test_hosted_scalar_allocator_placement(tmp_path):
    execute(tmp_path, 'scalar-allocator-placement', codegen(SrcFile.from_path(SCALAR_PLACEMENT), debug_locations=False))


def test_native_scalar_allocator_placement(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SCALAR_PLACEMENT.read_text()], errors=[])


PLACEMENT_FALLBACKS = [
    '''build=():>int64=>{let xs:array<int64>=[] xs.push(42) return xs.length}
work=(callback:():>int64 @arena:Arena):>int64=>$allocator(@arena) {callback()}
main=():>int64=>{let arena=Arena[] let n=work(@build @arena) return if arena.handle=?0 and n=?1 42 else 1}''',
    '''main=():>int64=>{
let captured:array<int64>=[42]
let arena=Arena[]
read=():>int64=>captured.length
let n=$allocator(@arena) {read()}
return if arena.handle=?0 and n=?1 42 else 1
}''',
]


@pytest.mark.parametrize('source', PLACEMENT_FALLBACKS)
def test_hosted_allocator_unknown_lifetime_falls_back(tmp_path, source):
    code=codegen(SrcFile(None, source), debug_locations=False)
    assert lower.last_placement_notes
    execute(tmp_path, 'allocator-fallback', code)
