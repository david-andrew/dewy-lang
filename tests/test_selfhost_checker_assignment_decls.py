"""Implicit declarations distinguish new bindings, discard slots and writes to visible constants or functions."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_assignment_decls_twins(compiler, tmp_path, monkeypatch):
    paths = (
        'tests/cases/unpack/implicit.dewy',
        'tests/cases/unpack/global_discard.dewy',
        'tests/cases/unpack/leaf_reassignment.dewy',
        'tests/cases/unpack/leaf_constant_write.dewy',
        'tests/cases/constant/shadowable_function_assign.dewy',
    )
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_assignment_decls',), paths)
    assert [r[2] == 0 for r in results] == [True, True, False, False, False]
