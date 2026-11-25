"""Stores follow aliases to their root, keep matching payloads and invalidate stale tag evidence."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_narrow_writes_twins(compiler, tmp_path, monkeypatch):
    paths = (
        'tests/cases/refine_alias_tags/tag_alias_union_ok.dewy',
        'tests/cases/refine_alias_tags/tag_alias_union_reject.dewy',
        'tests/cases/refine_alias_tags/alias_guard_root_write.dewy',
        'tests/cases/refine_alias_tags/same_member.dewy',
    )
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_narrow_writes',), paths)
    assert [r[2] == 0 for r in results] == [True, False, True, True]
