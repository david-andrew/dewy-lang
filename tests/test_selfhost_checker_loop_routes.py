"""Check the named route and source binding in value-iteration diagnostics."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_loop_routes_twins(compiler, tmp_path, monkeypatch):
    paths = ('tests/cases/loop/value_resize.dewy', 'tests/cases/loop/value_resize_field.dewy',
             'tests/cases/loop_copy/record_copy.dewy')
    rows = compare_builds(compiler, tmp_path, monkeypatch, ('checker_loop_routes',), paths)
    assert all(r[2] != 0 and 'changes the length of' in r[4] for r in rows[:2])
    assert rows[2][2] == 0
