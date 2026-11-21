"""Typed and nested patterns extract the same leaves and check the same initializer as the twin."""
from tools.cases import parse
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_checker_binding_inputs_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = sorted((ROOT / 'tests/cases/unpack').glob('*.dewy'))
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_binding_inputs',), cases)
    for path, _, status, *_ in results:
        assert (status != 0) == (parse(ROOT / path).kind == 'reject'), path
    assert any(r[2] == 0 for r in results) and any(r[2] != 0 for r in results)
