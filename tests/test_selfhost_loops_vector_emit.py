"""Vector splats and guarded AVX/SSE emission match their frozen Jo twin."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_loops_vector_emit_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    results = compare_builds(
        compiler, tmp_path, monkeypatch, ('loops_vector_emit',),
        ('tests/ladder/96_ct_crypto/design.dewy',
         'tests/ladder/100_rtos_kernel/design.dewy',
         'tests/ladder/101_ml_training/core.dewy',
         'tests/cases/optimizer/vector_operand_values.dewy',
         'tests/cases/product_bounds/vector_lanes.dewy',
         'tests/cases/product_bounds/vector_lane_written.dewy',
         'tests/cases/product_bounds/row_major.dewy',
         'compiler/main.jo'),
        flags=((), ('--release',)),
    )
    assert len(results) == 16
    assert all(results[i][2] == 0 for i in (0, 1, 2, 3, 4, 5, 14, 15))
