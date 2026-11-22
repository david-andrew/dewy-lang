"""Preparing storage boundaries, shifts, loops and shader bodies match the frozen Jo implementation."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_exact_preparation_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [p.relative_to(ROOT) for group in ('exact_int', 'exact_loops', 'fixed', 'gpu_integer_ops', 'progress_entries')
             for p in sorted((ROOT / 'tests/cases' / group).glob('*.dewy'))
             if p.with_suffix('.out').exists() or p.with_suffix('.err').exists()]
    programs = [*cases, 'tests/ladder/100_rtos_kernel/design.dewy', 'compiler/main.jo']
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_preparation',), programs,
                             flags=((), ('--release',)))
    assert len(results) == 2 * len(programs)
    assert all(r[2] == 0 for r in results[-4:])
    assert any(r[2] != 0 for r in results)
