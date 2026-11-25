"""Enum ordinal conversion and dialect-dependent ordering match the Jo checker."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_enum_expressions_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    ordinary = tmp_path / 'ordinal.jo'
    ordinary.write_text('enum Key: left, right\nmain = (): print(int(Key(1)))\n')
    sparse = tmp_path / 'sparse.jo'
    sparse.write_text('enum Key: left = 4, right = 7\nmain = (): print(int(Key(4)))\n')
    unordered = tmp_path / 'order.dewy'
    unordered.write_text("Key:type='left' | 'right'\nbefore=(a:Key b:Key):>bool=>a <? b\nmain=()=>printl(before('left' 'right'))\n")
    paths = ['tests/fixtures/upstream/enum_union.jo', ordinary, sparse, unordered]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('enum_expressions',), paths)
    assert [r[2] == 0 for r in results] == [True, True, False, False]
    assert 'variants numbered 0, 1, 2' in results[-2][4]
    assert 'members of a union of string literals are unordered' in results[-1][4]
