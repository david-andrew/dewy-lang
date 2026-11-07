"""GLSL emission helpers (types, zero values, structs, uniform layouts, buffer readers, narrowing, float to
integer, signed division, shifts, blocks and names) agree with frozen Jo in compiled shader programs."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'draw_context/direct',
    'draw_context/helpers',
    'game/polyline_joins',
    'gpu_capacity/draw',
    'dogfood/91_markov_weather',
    'gpu_broadcast/guard_elements',
    'gpu_broadcast/checked_at_run_time',
    'gpu_broadcast/known_shapes',
    'gpu_ieee/kernel_min_nan',
    'gpu_ieee/kernel_max_zero',
    'gpu_ieee/vector_nan',
]


def test_glsl_emit_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
