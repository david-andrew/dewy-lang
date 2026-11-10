"""Rare expression hints (`as` and `??` regrouping, private and unused-file names, Dewy spellings of
builtin names, map_args, duration and element-gap notes, refuted literal contracts, Canceled in a
coalesce) agree with frozen Jo: the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('regroup_hints', 'coalesce', 'coalesce_jump', 'cancel_defaults', 'explicit_cancellation', 'errors', 'secret',
        'self_length', 'units', 'named', 'fmt', 'dogfood37_proofs')


def test_expr_hints_match_twin(compiler, tmp_path, monkeypatch):
    files = [p for d in DIRS for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    paths = [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('expr_hints',), paths)
    assert sum(r[2] == 0 for r in results) > 50 and sum(r[2] != 0 for r in results) > 50
