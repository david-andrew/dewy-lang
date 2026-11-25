"""Closure bodies, captured aliases, generic callbacks and task results match the frozen checker."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_lambda_body_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [p for group in ('closure', 'task_capture', 'tasks')
             for p in sorted((ROOT / 'tests/cases' / group).glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_lambda_body',), cases)
    assert all((status != 0) == (ROOT / path).with_suffix('.err').is_file() for path, _, status, *_ in results)
    assert any(r[2] for r in results) and any(r[2] == 0 for r in results)
