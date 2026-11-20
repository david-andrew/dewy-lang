"""Loop versioning and the vectorization entry match their frozen Jo twin."""

from pathlib import Path

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_loops_version_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    # Bounds-checked counting loops, shifted and affine indexes, overflow
    # obligations and vector plans, in default (vectorizing) and release
    # (versioning every function) builds, plus the compiler itself.
    bounds = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'tests/cases/optimizer').glob('bounds_*.dewy'))
    programs = ('tests/ladder/96_ct_crypto/design.dewy',
                'tests/ladder/101_ml_training/core.dewy',
                'tests/cases/optimizer/vector_operand_values.dewy',
                'tests/cases/product_bounds/vector_lanes.dewy',
                'tests/cases/product_bounds/row_major.dewy',
                'tests/cases/product_bounds/row_major_int32.dewy',
                *bounds[:12],
                'compiler/main.jo')
    assert all(Path(ROOT / p).is_file() for p in programs)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('loops_version',), programs,
                             flags=((), ('--release',)))
    assert len(results) == 2 * len(programs)
    assert results[0][2] == 0 and results[-1][2] == 0 and results[-2][2] == 0
