"""Owned string locals transfer without invalidating earlier views or loops."""
from pathlib import Path

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_string_storage_moves_preserve_values_and_cleanup(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/string_storage_moves.dewy')
    code = codegen(source, debug_locations=False)
    notes = [note for note in lower.last_move_notes if note.srcfile.path == source.path]
    for name in ['first', 'second', 'third', 'fourth', 'immutable']:
        assert any(f'`{name}` is moved into owned storage' in note.message for note in notes)
    for name in ['live', 'repeated', 'owner']:
        assert not any(f'`{name}` is moved into owned storage' in note.message for note in notes)
    execute(tmp_path, 'string-storage-moves', code)


def test_string_move_removes_storage_cost_with_positive_control(tmp_path, monkeypatch):
    source = SrcFile(None, '''
exercise=(value:string):>int64=>{
    let items:array<string>=[]
    items.push('capacity')
    let text=value.copy()
    let before:int64=_arena_allocated_bytes
    items[0]=text
    let allocated:int64=_arena_allocated_bytes-before
    $runtime_assert items[0]=?value
    return allocated
}
main=():>int64=>{
    printl(exercise("value {42}"))
    return 42
}
''')
    optimized = codegen(source, debug_locations=False)
    with monkeypatch.context() as patch:
        patch.setattr(lower._Lowerer, '_compute_moves', lambda *args: set())
        baseline = codegen(source, debug_locations=False)
    for fast, slow in zip(execute(tmp_path, 'moved', optimized), execute(tmp_path, 'copied', baseline)):
        assert int(fast.stdout) == 0
        assert int(slow.stdout) > 0
