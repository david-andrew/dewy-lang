"""Candidate indexes must preserve exhaustive matching, including ambiguity."""
from pathlib import Path
import pickle

import pytest

from dewy.parser import t0, t1
from dewy.reporting import ReportException, SrcFile
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


@pytest.mark.parametrize('source', CASES + [
    '₁x 0x[face 1e2] 1e10 1p10',
    '$"!?"body!? $r"END"rawEND $t"END"${1}END',
])
def test_character_candidates_preserve_exhaustive_tokens(source, monkeypatch):
    file = SrcFile(None, source)
    indexed = pickle.dumps(t0.tokenize(file))
    candidates = t0.get_allowed_tokens
    monkeypatch.setattr(t0, 'get_allowed_tokens', lambda context, first=None: candidates(context))
    # Includes payloads, locations, and opener/closer links, not just token kinds.
    assert pickle.dumps(t0.tokenize(file)) == indexed


@pytest.mark.parametrize('source', [
    '#{ unfinished', '"unfinished', '"\\u12"', '$"unfinished',
    '0rABC', '<a >> b>', ']', '"\\unknown"', 'a\rb', '\x01',
])
def test_character_candidates_preserve_diagnostics(source, monkeypatch, capsys):
    def outcome():
        try:
            result = pickle.dumps(t0.tokenize(SrcFile(None, source)))
        except (ReportException, SystemExit) as error:
            result = type(error), str(error)
        return result, capsys.readouterr()

    indexed = outcome()
    candidates = t0.get_allowed_tokens
    monkeypatch.setattr(t0, 'get_allowed_tokens', lambda context, first=None: candidates(context))
    assert outcome() == indexed


def test_character_candidates_preserve_extension_matchers(monkeypatch):
    class Inherited(t0.Identifier):
        pass

    class Changed(t0.Identifier):
        @staticmethod
        def eat(src, ctx):
            return 1 if src.startswith('~') else None

    class Declared(Changed):
        first_chars = frozenset('~')

    classes = [Inherited, Changed, Declared, t0.Number]
    monkeypatch.setattr(t0, 'descendants', lambda parent: classes)
    t0.get_allowed_tokens.cache_clear()
    try:
        assert t0.get_allowed_tokens(t0.Root) == classes
        assert t0.get_allowed_tokens(t0.Root, '~') == [Changed, Declared, t0.Number]
        assert t0.get_allowed_tokens(t0.Root, 'x') == [Inherited, Changed, t0.Number]
        assert t0.get_allowed_tokens(t0.StringBody, '~') == []
    finally:
        t0.get_allowed_tokens.cache_clear()
