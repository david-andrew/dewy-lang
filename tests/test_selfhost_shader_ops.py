"""GLSL and Metal shader helpers (types, names, locals, wrapping, helper declarations, contexts) agree with
frozen Jo in compiled shader programs, for this machine and cross-compiled for a Mac."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'draw_context/direct',
    'game/polyline_joins',
    'gpu_capacity/draw',
    'dogfood/91_markov_weather',
    'gpu_broadcast/guard_elements',
    'gpu_broadcast/known_shapes',
]


def test_shader_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0


def test_shader_ops_metal_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES, ('--target', 'aarch64-mac')) > 0
