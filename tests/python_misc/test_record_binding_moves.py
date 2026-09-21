"""Records transfer at last use without cloning their nested owned fields."""
from pathlib import Path

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

SOURCE = Path(__file__).resolve().parents[1] / 'fixtures/record_binding_moves.dewy'


def test_record_binding_moves_allocate_nothing_and_keep_views_live(tmp_path, monkeypatch):
    source = SrcFile.from_path(SOURCE)
    optimized = codegen(source, debug_locations=False)
    notes = [note.message for note in lower.last_move_notes if note.moved and note.srcfile.path == source.path]
    assert any('`first` is moved when bound to `second`' in note for note in notes)
    assert any('`second` is moved when bound to `third`' in note for note in notes)
    assert not any('`source` is moved when bound to `copy`' in note for note in notes)
    with monkeypatch.context() as patch:
        patch.setattr(lower._Lowerer, '_compute_moves', lambda *args: set())
        baseline = codegen(source, debug_locations=False)
    for fast, slow in zip(execute(tmp_path, 'record-moved', optimized), execute(tmp_path, 'record-copied', baseline)):
        assert int(fast.stdout) == 0
        assert int(slow.stdout) > 0


def test_native_record_binding_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text

    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE.read_text()], errors=[], outputs=['0\n'])
