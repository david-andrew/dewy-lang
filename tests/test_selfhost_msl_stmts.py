"""Metal statements, expressions, arithmetic, buffer reads and writes, atomics, stage and kernel
builds agree with frozen Jo: the GPU cases built for macOS, with the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

CASES = '''dogfood/91_markov_weather game/headless_window game/polyline_batches game/polyline_degenerate
game/polyline_joins'''.split()


def test_msl_stmts_match_twin(compiler, tmp_path, monkeypatch):
    dirs = [p for d in ('gpu', 'gpu_broadcast', 'draw_context', 'gpu_capacity', 'gpu_ieee', 'gpu_float_sum', 'gpu_integer_upload')
            for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    paths = [str(p.relative_to(ROOT)) for p in dirs] + [f'tests/cases/{c}.dewy' for c in CASES]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('msl_stmts',), paths, (('--target', 'aarch64-mac'),))
    built = [r for r in results if r[2] == 0]
    assert len(built) > 10 and any(b'metal_stdlib' in data for r in built for data in r[5].values())
