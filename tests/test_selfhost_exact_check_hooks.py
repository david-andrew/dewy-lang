"""Checked operations, conversion arms and format words match the frozen Jo implementation."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_exact_check_hooks_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [p.relative_to(ROOT) for group in ('exact_int', 'fixed', 'wrap_uint64_narrowing')
             for p in sorted((ROOT / 'tests/cases' / group).glob('*.dewy'))
             if p.with_suffix('.out').exists() or p.with_suffix('.err').exists()]
    programs = [*cases, 'tests/cases/word_format_local/finite.dewy',
                'tests/ladder/100_rtos_kernel/design.dewy', 'compiler/main.jo']
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_check_hooks',), programs,
                             flags=((), ('--release',)))
    assert len(results) == 2 * len(programs)
    assert all(r[2] == 0 for r in results[-6:])
    assert any(r[2] != 0 for r in results)
