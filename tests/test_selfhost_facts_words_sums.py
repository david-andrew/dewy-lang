"""GPU code's 64-bit words and buffer lengths (glsl_ops, facts_values), narrow sums' fit
obligation (facts_library), parallel collections' lengths (facts_capture) and loop widening's
constant thresholds (facts_loops) agree with frozen Jo: the same programs, messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('glsl_ops', 'facts_values', 'facts_library', 'facts_capture', 'facts_loops')


def test_facts_words_sums_match_twin(compiler, tmp_path, monkeypatch):
    dirs = ('gpu_fact_words', 'sum_narrow', 'parallel_length', 'loop_thresholds', 'gpu_buffer_bounds')
    paths = [str(p.relative_to(ROOT)) for d in dirs for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch, LEAVES, paths)
    assert sum(r[2] == 0 for r in results) >= 8 and sum(r[2] != 0 for r in results) >= 4
