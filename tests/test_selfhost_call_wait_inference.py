"""Generic calls in array literals receive the same contextual types through both leaves."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_call_wait_inference_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = sorted((ROOT / 'tests/cases/generic').glob('array_literal_*.dewy'))
    results = compare_builds(compiler, tmp_path, monkeypatch, ('call_wait_inference',), cases)
    assert cases
    for case, result in zip(cases, results, strict=True):
        assert (result[2] == 0) == (not case.with_suffix('.err').exists()), case.name
