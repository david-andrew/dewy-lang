"""Shared imports are loaded once and a missing import retains its source diagnostic."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_load_module_twins(compiler, tmp_path, monkeypatch):
    missing = tmp_path / 'missing.jo'
    missing.write_text("use 'does_not_exist.jo'\nmain = ():\n    pass\n")
    paths = ('tests/cases/modules/cycle_diamond.dewy', 'tests/cases/modules/cycle_jo_exempt.dewy', missing)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_load_module',), paths)
    assert results[0][2] == results[1][2] == 0
    assert results[-1][2] != 0 and 'does_not_exist' in results[-1][4]
