"""Module registration binds declarations once and resolves named, selective and missing imports."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_module_decls_twins(compiler, tmp_path, monkeypatch):
    missing = tmp_path / 'missing.jo'
    missing.write_text("use 'missing_dependency.jo'\nmain = (): print(1)\n")
    paths = ('tests/cases/modules/import_lists.dewy', 'tests/cases/modules/cycle_diamond.dewy',
             'tests/cases/unpack/global.dewy', 'tests/cases/import_cycles/self_import.dewy', missing)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_module_decls',), paths)
    assert all(r[2] == 0 for r in results[:-1])
    assert results[-1][2] != 0 and "cannot find 'missing_dependency.jo'" in results[-1][4]
