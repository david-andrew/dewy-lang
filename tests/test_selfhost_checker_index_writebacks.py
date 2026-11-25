"""End-relative selectors and pool element fields write back through the same evaluated place."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_index_writebacks_twins(compiler, tmp_path, monkeypatch):
    paths = (
        'tests/cases/end/index_update_order.dewy',
        'tests/cases/end/index_update_nested.dewy',
        'tests/cases/pool_fixed_update/selector_call_keeps_writeback.dewy',
        'tests/cases/pool_fixed_update/refined_element_store.dewy',
    )
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_index_writebacks',), paths)
    assert [r[2] == 0 for r in results] == [True, True, True, False]
