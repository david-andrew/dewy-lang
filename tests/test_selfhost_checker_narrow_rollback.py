"""Sibling arms and terminating arms restore the same narrowed locals as the frozen checker."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_narrow_rollback_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    paths = sorted((ROOT / 'tests/cases/optional').glob('union_else_narrowing*.dewy'))
    paths += sorted((ROOT / 'tests/cases/semicolon_narrow').glob('*.dewy'))
    paths += sorted((ROOT / 'tests/cases/match').glob('union*.dewy'))
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_narrow_rollback',), paths)
    for path, _, status, *_ in results:
        assert (status != 0) == (ROOT / path).with_suffix('.err').is_file(), path
    assert any(r[2] for r in results) and any(r[2] == 0 for r in results)
