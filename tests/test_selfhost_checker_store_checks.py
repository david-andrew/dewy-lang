"""Declarations, refinement stores, tuple values and updates select the same write checks."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_store_checks_twins(compiler, tmp_path, monkeypatch):
    paths = ('tests/cases/unpack/implicit.dewy', 'tests/cases/compound/array_place.dewy',
             'tests/cases/refinements/container_store.dewy', 'tests/cases/unpack/leaf_constant_write.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_store_checks',), paths)
    assert results[0][2] == results[1][2] == 0
    assert results[-1][2] != 0
