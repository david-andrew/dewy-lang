"""Date range loops reach the calendar checker from either compiler build."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_date_range_twin(compiler, tmp_path, monkeypatch):
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_for_loops',), [
        'tests/cases/dogfood37_proofs/date_range_loop_named.dewy',
    ])
    assert results[0][2] == 0
