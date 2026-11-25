"""Context-free exact widths (constants, folding, bindings, conversions, masks,
remainders, shifts and midpoints) match their frozen Jo twin."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_exact_static_widths_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    # Every exact-integer case (constant widths and folds, bound constants,
    # masks, remainders, literal shifts and the rejections), the flagships that
    # store exact words, and the compiler.
    cases = sorted(str(p.relative_to(ROOT)) for pattern in ('exact_int/*.dewy', 'exact_loops/*.dewy', 'fixed/*.dewy')
                   for p in (ROOT / 'tests/cases').glob(pattern))
    programs = (*cases,
                'tests/ladder/96_ct_crypto/design.dewy',
                'tests/ladder/100_rtos_kernel/design.dewy',
                'tests/ladder/101_ml_training/core.dewy',
                'compiler/main.jo')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_static_widths',), programs,
                             flags=((), ('--release',)))
    assert len(results) == 2 * len(programs) and len(cases) > 50
    assert sum(r[2] == 0 for r in results) > len(programs)
    assert results[-1][2] == 0 and results[-2][2] == 0
