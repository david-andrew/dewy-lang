"""Nested compile-time arms preserve statement order and block result checking."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_block_entries_twins(compiler, tmp_path, monkeypatch):
    selected = tmp_path / 'when.jo'
    selected.write_text('main = ():\n    n = 3\n    when true:\n        when false:\n'
                        '            not_a_function()\n        else:\n            n += 2\n'
                        '    when false:\n        missing()\n    print(n)\n')
    rows = compare_builds(compiler, tmp_path, monkeypatch, ('checker_block_entries',),
                          (selected, 'tests/cases/match/void_union_trailing_test.dewy'))
    assert all(r[2] == 0 for r in rows)
