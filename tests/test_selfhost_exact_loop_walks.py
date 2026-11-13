"""Exact-int loop plans (guarded reductions, broadcast map censuses and generated array drops) agree with
frozen Jo: the same messages and bytes, in default and release builds and for the compiler itself."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

GLOBS = ('exact_int/*.dewy', 'optimizer/guarded_array_*.dewy', 'numeric/broadcast_*.dewy', 'numeric/matrix_*.dewy',
         'facts/nd_*.dewy', 'broadcast_facts/*.dewy', 'comprehension/broadcast_statement.dewy')


def test_exact_loop_walks_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    files = [p for g in GLOBS for p in sorted((ROOT / 'tests/cases').glob(g))]
    paths = [str(p.relative_to(ROOT)) for p in dict.fromkeys(files)]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_loop_walks',), paths,
                             flags=((), ('--release',)))
    assert sum(r[2] == 0 for r in results) > 80 and sum(r[2] != 0 for r in results) > 10


def test_exact_walks_self_build_matches_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    leaves = ('exact_loop_walks', 'exact_reset_walks', 'exact_chain_walks', 'exact_words', 'exact_raw_plans')
    results = compare_builds(compiler, tmp_path, monkeypatch, leaves, ('compiler/main.jo',), flags=(('--release',),))
    assert results[0][2] == 0
