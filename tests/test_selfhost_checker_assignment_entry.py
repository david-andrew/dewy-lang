"""Assignment setup preserves end-index updates and diagnoses a write to a later same-file global."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_assignment_entry_twins(compiler, tmp_path, monkeypatch):
    late = tmp_path / 'late.jo'
    late.write_text('update_score = ():\n    score = 2\nscore = 1\nmain = ():\n    update_score()\n    print(score)\n')
    paths = ('tests/cases/end/index_update.dewy', 'tests/cases/pool_fixed_update/direct_update_snapshot.dewy', late)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_assignment_entry',), paths)
    assert all(r[2] == 0 for r in results[:-1])
    assert results[-1][2] != 0 and "global variable declared below this function" in results[-1][4]
