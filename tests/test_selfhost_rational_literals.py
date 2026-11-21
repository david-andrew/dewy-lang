"""Decimal and rational construction preserves word folds, big literals and divisor diagnostics."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_rational_literals_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = ('decimal_text_exact', 'word', 'word_narrowing', 'division_widths', 'word_from_rational')
    paths = [f'tests/cases/rational/{case}.dewy' for case in cases]
    big_literal = tmp_path / 'big_literal.dewy'
    big_literal.write_text('main=()=>{let n:rational=0.12345678901234567890123456789; printl(n)}\n')
    paths.insert(0, big_literal)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('rational_literals',), paths,
                             flags=((), ('--release',)))
    assert [r[2] == 0 for r in results] == [True] * 10 + [False] * 2
