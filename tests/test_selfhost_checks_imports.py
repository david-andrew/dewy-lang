"""Import binding, clashes and splat shadowing agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'modules/splat_selective_collision',
    'modules/splat_collision',
    'modules/splat_own',
    'batch4_entry/splat',
    'rational/library_name',
]


def test_checks_imports_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
