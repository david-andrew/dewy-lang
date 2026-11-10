"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/gpu_word_memory/exact_loops.dewy',
    'tests/cases/gpu_buffer_bounds/unguarded_read_bad.dewy',
    'tests/cases/gpu_word_memory/exact_overflow_bad.dewy',
)


def test_gpu_type_checks_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('gpu_type_checks',), PATHS)
