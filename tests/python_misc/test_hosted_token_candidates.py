"""Candidate indexes must preserve exhaustive matching, including ambiguity."""
from pathlib import Path

import pytest

from dewy.parser import t0, t1
from dewy.reporting import SrcFile
from test_bootstrap_parser import SOURCES, hosted_t1_dump

ROOT = Path(__file__).resolve().parents[2]
CASES = SOURCES + [path.read_text() for path in sorted((ROOT / 'dewy/bootstrap/tests').glob('*.dewy'))]


@pytest.mark.parametrize('source', CASES)
def test_indexed_candidates_preserve_exhaustive_tokens(source, monkeypatch):
    file = SrcFile(None, source)
    indexed = hosted_t1_dump(t1.tokenize(file))
    monkeypatch.setattr(t1, 'candidates', lambda first: t1.top_level_tokens)
    assert hosted_t1_dump(t1.tokenize(file)) == indexed


def test_candidates_honor_subclasses_and_unfiltered_extensions(monkeypatch):
    class Identifier(t0.Identifier):
        pass

    class Extension(t1.InedibleToken):
        pass

    monkeypatch.setattr(t1, 'top_level_tokens', [*t1.top_level_tokens, Extension])
    t1.candidates.cache_clear()
    try:
        assert t1.candidates(Identifier) == (t1.Identifier, t1.Keyword, t1.Bool, t1.Operator, Extension)
        assert Extension in t1.candidates(t0.StringChars)
    finally:
        t1.candidates.cache_clear()


def test_symbol_prefix_index_preserves_longest_match():
    context = t0.Root(SrcFile(None, ''), [])
    for spelling in ['', 'unknown', *t0.symbols, *(symbol + 'tail' for symbol in t0.symbols)]:
        expected = next((len(symbol) for symbol in t0.symbols if spelling.startswith(symbol)), None)
        assert t0.Symbol.eat(spelling, context) == expected
