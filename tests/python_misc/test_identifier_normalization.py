"""Identifier aliases preserve the decided distinctions and source locations."""
import pytest

from dewy.parser import t0, t1
from dewy.reporting import SrcFile


@pytest.mark.parametrize('source,canonical', [
    ('x_12', 'x₁₂'), ('x_1_2', 'x₁₂'), ('x₁₂', 'x₁₂'),
    ('x‾12', 'x¹²'), ('x‾1‾2', 'x¹²'), ('x¹²', 'x¹²'),
    ('foo_2_bar', 'foo₂_bar'), ('_2V_3‾1', '₂V₃¹'),
    ('µ', 'μ'), ('µs', 'μs'), ('μs', 'μs'),
    ('foo_bar', 'foo_bar'), ('__load_i64__', '__load_i64__'),
    ('x1', 'x1'), ('x_i', 'x_i'), ('xᵢ', 'xᵢ'), ('xᵀ', 'xᵀ'),
    ('x‾T', 'x‾T'), ('A', 'A'), ('Α', 'Α'),
])
def test_identifier_name_and_source_span(source, canonical):
    srcfile = SrcFile(None, source)
    raw = t0.tokenize(srcfile)
    tokens = t1.tokenize(srcfile)
    assert len(raw) == len(tokens) == 1
    assert raw[0].src == source
    assert isinstance(tokens[0], t1.Identifier)
    assert tokens[0].name == canonical
    assert tokens[0].loc == raw[0].loc


def test_strings_do_not_normalize_identifier_spelling():
    tokens = t1.tokenize(SrcFile(None, "'x_12 µ x‾12'"))
    assert tokens[0].content == 'x_12 µ x‾12'


def test_normalized_bindings_execute(tmp_path):
    from pathlib import Path
    from dewy.backend.udewy import codegen
    from tests.python_misc.test_scalar_projection import execute
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/identifier_normalization.dewy'
    execute(tmp_path, 'normalized-bindings', codegen(SrcFile.from_path(fixture)))
