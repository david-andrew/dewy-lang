"""The move rule: last uses of owned array (and object) locals at transfer sites are moves; other transfers are copies."""
from pathlib import Path

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile

REPO_ROOT = Path(__file__).resolve().parents[2]


def _notes(source: str) -> list[tuple[str, bool]]:
    codegen(SrcFile(None, source))
    return [(note.message.split('`')[1], note.moved) for note in lower.last_move_notes]


def test_last_uses_move_and_later_uses_copy() -> None:
    notes = _notes((REPO_ROOT / 'dewy' / 'tests' / 'array_moves.dewy').read_text())
    assert ('out', True) in notes          # returned at its last use
    assert ('items', True) in notes        # stored into a field at its last use
    assert ('box', True) in notes          # an object returned at its last use adopts its arrays
    assert ('xs', False) in notes          # used again after the store


def test_a_store_inside_a_loop_is_not_a_move() -> None:
    notes = _notes(
        'let Box:type = [items:array<int64>]\n'
        'let f = (n:int64):>int64 => {\n'
        '    let xs:array<int64> = []\n'
        '    let count:int64 = 0\n'
        '    loop count <? n { let box:Box = [items = xs]  count += box.items.length + 1 }\n'
        '    return count\n'
        '}\n'
        'let main = ():>int64 => f(3)\n'
    )
    assert ('xs', False) in notes          # the next iteration uses it again


def test_a_return_inside_a_loop_is_a_move() -> None:
    notes = _notes(
        'let f = (n:int64):>array<int64> => {\n'
        '    let xs:array<int64> = []\n'
        '    let count:int64 = 0\n'
        '    loop count <? n { xs.push(count)  if count =? 2 { return xs }  count += 1 }\n'
        '    return xs\n'
        '}\n'
        'let main = ():>int64 => f(5).length\n'
    )
    # a return leaves the function whatever follows it in the text: both returns move
    assert notes.count(('xs', True)) == 2 and notes.count(('xs', False)) == 0


def test_owned_descriptor_moves_into_another_binding(tmp_path):
    from tests.python_misc.test_scalar_projection import execute
    source = SrcFile.from_path(REPO_ROOT / 'tests/fixtures/array_binding_moves.dewy')
    code = codegen(source, debug_locations=False)
    notes = [note.message for note in lower.last_move_notes if note.moved and note.srcfile.path == source.path]
    assert any('`first` is moved when bound to `second`' in note for note in notes)
    assert any('`copied` is moved when bound to `third`' in note for note in notes)
    assert not any('`boxes` is moved when bound to `taken`' in note for note in notes)
    execute(tmp_path, 'array-binding-moves', code)


def test_heap_descriptor_transfer_allocates_nothing(tmp_path, monkeypatch):
    from tests.python_misc.test_scalar_projection import execute
    source = SrcFile(None, '''
make=():>array<int64>=>[42]
exercise=():>int64=>{
    let first=make()
    let shared=first.copy()
    let before:int64=_arena_allocated_bytes
    let second:array<int64>=first
    let allocated:int64=_arena_allocated_bytes-before
    second.push(1)
    second[0]=99
    if shared.length <? 1 return -1
    if shared[0] not=?42 return -2
    return allocated
}
main=():>int64=>{
    printl(exercise())
    return 42
}
''')
    optimized = codegen(source, debug_locations=False)
    with monkeypatch.context() as patch:
        patch.setattr(lower._Lowerer, '_compute_moves', lambda *args: set())
        baseline = codegen(source, debug_locations=False)
    for fast, slow in zip(execute(tmp_path, 'array-moved', optimized), execute(tmp_path, 'array-copied', baseline)):
        assert int(fast.stdout) == 0
        assert int(slow.stdout) > 0
