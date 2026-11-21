"""Shader word checks (glsl_ops' sl_word_check and sl_exact_range, through the GLSL, Metal and
SPIR-V statements), the facts' ranges they read (facts_capture) and GPU code's proof-only help
(witness_ops, exact_fact_transfer; the ranges exact_preparation demands) agree with frozen Jo: the same programs, messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('glsl_ops', 'glsl_stmts', 'msl_stmts', 'spirv_stmts', 'facts_capture', 'witness_ops', 'exact_preparation', 'exact_fact_transfer')


def test_glsl_ops_words_match_twin(compiler, tmp_path, monkeypatch):
    dirs = ('gpu_fact_words', 'gpu_programs', 'gpu_word_memory', 'gpu_integer_ops', 'gpu_buffer_bounds')
    paths = [str(p.relative_to(ROOT)) for d in dirs for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch, LEAVES, paths)
    assert sum(r[2] == 0 for r in results) > 15 and sum(r[2] != 0 for r in results) >= 3
