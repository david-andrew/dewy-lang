"""GLSL statements, expressions, arithmetic, buffer reads, vertex and fragment stages, kernels and
struct hoisting agree with frozen Jo: the same shader programs, messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

CASES = '''dogfood/91_markov_weather game/headless_window game/polyline_batches game/polyline_degenerate
game/polyline_joins'''.split()


def test_glsl_stmts_match_twin(compiler, tmp_path, monkeypatch):
    dirs = [p for d in ('gpu', 'gpu_broadcast', 'draw_context', 'gpu_capacity', 'gpu_ieee', 'gpu_float_sum', 'gpu_integer_upload')
            for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    paths = [str(p.relative_to(ROOT)) for p in dirs] + [f'tests/cases/{c}.dewy' for c in CASES]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('glsl_stmts',), paths)
    assert sum(r[2] == 0 for r in results) > 10 and any(r[2] != 0 for r in results)
