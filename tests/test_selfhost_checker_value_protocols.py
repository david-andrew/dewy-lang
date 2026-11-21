"""Generated equality and hashing honor the same record and collection protocols as the frozen checker."""

from tools.cases import parse
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_checker_value_protocols_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [p for group in ('protocols', 'union_hash')
             for p in sorted((ROOT / 'tests/cases' / group).glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_value_protocols',), cases,
                             flags=((), ('--release',)))
    assert any(r[2] == 0 for r in results)
    for path, _, status, *_ in results:
        assert (status != 0) == (parse(ROOT / path).kind == 'reject'), path
