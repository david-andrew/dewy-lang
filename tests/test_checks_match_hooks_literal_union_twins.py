"""Literal-set preprocessing preserves bare generic outcome patterns in both frontends."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_checks_match_hooks_literal_union_twins(compiler, tmp_path, monkeypatch):
    paths = [str(p.relative_to(ROOT)) for p in
             sorted((ROOT / 'tests/cases/literal_union_outcomes').glob('*.dewy'))]
    result = compare_builds(compiler, tmp_path, monkeypatch,
                           ('checks_match_hooks',), paths,
                           flags=((), ('--release',)))
    assert result
    for path, _, code, *_ in result:
        assert (code != 0) == path.endswith("bad_name.dewy")
