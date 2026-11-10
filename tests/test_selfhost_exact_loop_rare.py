"""Rare exact-int loop lowering (guarded array reductions and their bounds, broadcast map producers,
parameters, widths, census and stride versions) agrees with frozen Jo: the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

GLOBS = ('exact_int/*.dewy', 'optimizer/guarded_array_*.dewy', 'numeric/broadcast_*.dewy', 'numeric/array_error_*.dewy',
         'numeric/matrix_*.dewy', 'facts/nd_*.dewy', 'facts/selection_ranges.dewy', 'draw_context/*.dewy',
         'game/polyline_*.dewy', 'broadcast_facts/*.dewy', 'compound/selectors_once.dewy', 'comprehension/broadcast_statement.dewy',
         'effects/dotted_lengths_no_traps.dewy', 'effects/power_exponent_no_traps.dewy', 'helpers/arrays.dewy',
         'self_length/forgetting_is_plain.dewy', 'gpu_capacity/draw.dewy')


def test_exact_loop_rare_matches_twin(compiler, tmp_path, monkeypatch):
    files = [p for g in GLOBS for p in sorted((ROOT / 'tests/cases').glob(g))]
    paths = [str(p.relative_to(ROOT)) for p in dict.fromkeys(files)]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_loop_rare',), paths)
    assert sum(r[2] == 0 for r in results) > 40 and sum(r[2] != 0 for r in results) > 10
