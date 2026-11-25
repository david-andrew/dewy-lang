"""Demand marks, decisions and representation flags match the frozen Jo implementation."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_exact_marks_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [p.relative_to(ROOT) for group in ('exact_int', 'exact_loops', 'notraps16_endpoints')
             for p in sorted((ROOT / 'tests/cases' / group).glob('*.dewy'))
             if p.with_suffix('.out').exists() or p.with_suffix('.err').exists()]
    programs = [*cases, 'tests/ladder/100_rtos_kernel/design.dewy', 'compiler/main.jo']
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_marks',), programs,
                             flags=((), ('--release',)))
    assert len(results) == 2 * len(programs)
    assert all(r[2] == 0 for r in results[-4:])
    assert any(r[2] != 0 for r in results)


def test_glsl_ops_reads_store_proofs(compiler, tmp_path, monkeypatch):
    cases = ('exact_store_guarded', 'exact_store_runtime_checks',
             'exact_store_unproven_bad', 'exact_store_wide_bad')
    paths = [f'tests/cases/gpu_integer_ops/{case}.dewy' for case in cases]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('glsl_ops',), paths)
    assert [r[2] == 0 for r in results] == [True, True, False, False]
