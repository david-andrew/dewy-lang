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
    # the return inside the loop is not the textually last use, so it copies; the final return moves
    assert notes.count(('xs', True)) == 1 and notes.count(('xs', False)) == 1
