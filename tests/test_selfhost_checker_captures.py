"""Closure capture chains, sharing diagnostics and narrowed aliases match the frozen checker."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_checker_captures_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [p for group in ('closure', 'task_capture') for p in sorted((ROOT / 'tests/cases' / group).glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_captures',), cases,
                             flags=((), ('--release',)))
    for path, _, status, *_ in results:
        assert (status != 0) == (ROOT / path).with_suffix('.err').is_file(), path
