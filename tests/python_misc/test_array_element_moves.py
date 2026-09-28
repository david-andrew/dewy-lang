"""Ordinary owned array rows use the same last-use rule as other stores."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from test_scalar_projection import execute

HEADER = 'make=():>array<int64>=>[42]\n'
PUSH = HEADER + '''main=():>int64=>{
    let value=make()
    let rows:array<array<int64>>=[]
    rows.push(value)
    return if rows.length>?0 and rows[0].length>?0 rows[0][0] else 1
}'''
MOVES = [PUSH,
    PUSH.replace('let rows:array<array<int64>>=[]\n    rows.push(value)', 'let rows:array<array<int64>>=[value]'),
    PUSH.replace('let rows:array<array<int64>>=[]\n    rows.push(value)',
                 'let rows:array<array<int64>>=[[1]]\n    if rows.length>?0 {rows[0]=value}'),
    PUSH.replace('rows.push(value)', 'rows.insert(value 0)'),
]
PRESERVE = HEADER + '''main=():>int64=>{
    let value=make()
    const held=@value
    let rows:array<array<int64>>=[value]
    if rows.length>?0 {rows[0].clear}
    return if held.length>?0 held[0] else 1
}'''
REPEATED = PUSH.replace('rows.push(value)', 'loop i in [0..2) {rows.push(value)}\n    if rows.length>?0 {rows[0].clear}').replace('rows[0].length>?0 rows[0][0]', 'rows.length>?1 and rows[1].length>?0 rows[1][0]')
BORROWED = HEADER + '''take=(source:array<int64>):>array<array<int64>>=>{
    const view=@source
    return [view]
}
main=():>int64=>{
    let original=make()
    let rows=take(original)
    if rows.length>?0 {rows[0].clear}
    return if original.length>?0 original[0] else 1
}'''
FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures/array_element_moves.dewy').read_text()


@pytest.mark.parametrize('source', MOVES)
def test_last_use_array_element_transfer(tmp_path, source):
    text = codegen(SrcFile(None, '$explicit_copies\n' + source), debug_locations=False)
    assert any(note.moved and 'stored in an element' in note.message for note in lower.last_move_notes)
    execute(tmp_path, 'array-element-move', text)


@pytest.mark.parametrize('source', [PRESERVE, REPEATED, BORROWED])
def test_array_element_snapshot_is_independent(tmp_path, source):
    execute(tmp_path, 'array-element-copy', codegen(SrcFile(None, source), debug_locations=False))
    with pytest.raises(UserError, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n' + source), debug_locations=False)


def test_array_element_move_allocates_nothing(tmp_path):
    execute(tmp_path, 'array-element-counter', codegen(SrcFile(None, FIXTURE), debug_locations=False))


def test_native_array_element_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    snapshots = [PRESERVE, REPEATED, BORROWED]
    check_structural_text(build_program_driver(tmp_path), tmp_path,
        cases=['$explicit_copies\n' + source for source in MOVES] + snapshots + [FIXTURE],
        errors=['$explicit_copies\n' + source for source in snapshots])
