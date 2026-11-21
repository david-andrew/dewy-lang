"""Exact store obligations, diagnostic witnesses and unsigned bounds match the frozen twin."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_exact_fact_transfer_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [path.relative_to(ROOT) for group in ('exact_int', 'uint64_ceiling', 'notraps16_endpoints')
             for path in sorted((ROOT / 'tests/cases' / group).glob('*.dewy'))
             if path.with_suffix('.out').exists() or path.with_suffix('.err').exists()]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_fact_transfer',), cases,
                             flags=((), ('--release',)))
    assert len(results) == 2 * len(cases)
    assert any(r[2] == 0 for r in results)
    assert any(r[2] and 'cannot prove exact integer result fits' in r[4] for r in results)
