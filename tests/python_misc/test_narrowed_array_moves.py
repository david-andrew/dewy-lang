"""Taking a narrowed array must empty its payload, not its owner cell."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from test_scalar_projection import execute
from test_union_local_moves import NARROWED_ARRAY, NARROWED_RETURN

HEADER = '''make=(flag:bool):>array<int64>|none=>if flag [42] else none
'''
BIND = HEADER + '''main=():>int64=>{
    let value=make(true)
    if value is? none return 1
    let taken:array<int64>=value
    return if taken.length>?0 taken[0] else 2
}'''
ELEMENT = BIND.replace('let taken:array<int64>=value\n    return if taken.length>?0 taken[0] else 2',
    'let rows:array<array<int64>>=[value]\n    return if rows.length>?0 and rows[0].length>?0 rows[0][0] else 2')
RETAG = HEADER + '''widen=():>array<int64>|int64|none=>{
    let value=make(true)
    if value is? none return 1
    return value
}
main=():>int64=>{
    let taken=widen()
    return if taken is? array<int64> and taken.length>?0 taken[0] else 2
}'''
PRESERVE = HEADER + '''main=():>int64=>{
    let value=make(true)
    if value is? none return 1
    const held=value
    let taken:array<int64>=value
    taken.clear
    return if held.length>?0 held[0] else 2
}'''
REPEATED = HEADER + '''main=():>int64=>{
    let value=make(true)
    if value is? none return 1
    let rows:array<array<int64>>=[]
    loop i in [0..2) {rows.push(value)}
    if rows.length>=?2 {rows[0].clear return if rows[1].length>?0 rows[1][0] else 3}
    return 2
}'''
FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures/narrowed_array_moves.dewy').read_text()
MOVES = [NARROWED_ARRAY, NARROWED_RETURN, BIND, ELEMENT, RETAG]


@pytest.mark.parametrize('source', MOVES)
def test_narrowed_array_payload_transfer(tmp_path, source):
    text = codegen(SrcFile(None, '$explicit_copies\n' + source), debug_locations=False)
    assert any(note.moved and ('empties the owning cell' in note.message
                              or 'its payload changes owner' in note.message)
               for note in lower.last_move_notes)
    execute(tmp_path, 'payload-take', text)


@pytest.mark.parametrize('source', [FIXTURE, PRESERVE, REPEATED])
def test_narrowed_array_lifetime_and_snapshots(tmp_path, source):
    execute(tmp_path, 'payload-lifetime', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', [PRESERVE, REPEATED])
def test_live_payload_cannot_satisfy_explicit_copies(source):
    with pytest.raises(UserError, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n' + source), debug_locations=False)


def test_native_narrowed_array_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
        cases=['$explicit_copies\n' + source for source in MOVES] + [FIXTURE, PRESERVE, REPEATED],
        errors=['$explicit_copies\n' + source for source in [PRESERVE, REPEATED]])
