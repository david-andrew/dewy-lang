"""The checked cursor summary and its fallback agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401


def test_facts_cursor_loops_twins(compiler, tmp_path, monkeypatch):
    cases = sorted('cursor_loops/' + p.stem
                   for p in (ROOT / 'tests/cases/cursor_loops').glob('*.dewy'))
    assert compare_facts(compiler, tmp_path, monkeypatch, cases,
                         leaves=('facts_loops', 'facts_lifecycle')) == 1
