"""A transfer that falls through to a return moves; loop exits and later uses keep copies."""
from pathlib import Path

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/exit_path_moves.dewy'


def test_exit_path_moves(tmp_path):
    source = SrcFile.from_path(FIXTURE)
    code = codegen(source, debug_locations=False)
    notes = [(note.message.split('`')[1], note.moved) for note in lower.last_move_notes if note.srcfile.path == source.path]
    assert notes.count(('early', True)) == 2, notes
    assert ('inner', True) in notes and ('found', True) in notes and ('lent_items', True) in notes, notes
    for name in ['kept', 'looped', 'stays']:
        assert (name, True) not in notes, (name, notes)
    execute(tmp_path, 'exit-path-moves', code)


def test_native_exit_path_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[FIXTURE.read_text()], errors=[])
