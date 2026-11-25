"""Final expressions, terminating arms and implicit void returns agree with the frozen checker."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_checker_body_end_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    paths = ('tests/cases/match/void_union_trailing_family.dewy',
             'tests/cases/match/void_union_trailing_test.dewy')
    missing = tmp_path / 'missing.dewy'
    missing.write_text('choose=(a:bool):>int64=>{if a {return 1}}\nmain=()=>printl(choose(true))\n')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_body_end',), (*paths, missing))
    assert all(r[2] == 0 for r in results[:-1])
    assert results[-1][2] != 0
