"""Nested array and map compound updates capture selectors and the receiver in evaluation order."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_selector_capture_twins(compiler, tmp_path, monkeypatch):
    paths = (
        'tests/cases/compound/selectors_once.dewy',
        'tests/cases/compound/map.dewy',
        'tests/cases/compound/nested_place.dewy',
        'tests/cases/assignment/effectful_index_before_rhs.dewy',
    )
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_selector_capture',), paths)
    assert [r[2] == 0 for r in results] == [True, True, True, True]
