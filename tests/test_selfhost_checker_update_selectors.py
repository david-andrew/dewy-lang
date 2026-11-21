"""Checked scalar reads and single evaluation of effectful compound selectors match the twin."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_update_selectors_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    paths = ('tests/cases/compound/selectors_once.dewy', 'tests/cases/facts/receiver_selector_once.dewy',
             'tests/cases/pool_fixed_update/selector_call_keeps_writeback.dewy',
             'tests/cases/dogfood28_proofs/update_selector_bounded.dewy',
             'tests/cases/dogfood28_proofs/update_selector_unbounded.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_update_selectors',), paths,
                             flags=((), ('--release',)))
    assert all(r[2] == 0 for r in results[:-2])
    assert all(r[2] != 0 for r in results[-2:])
