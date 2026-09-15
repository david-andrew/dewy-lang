"""String materialization inspects only the lengths demanded by its target."""
import pytest

from dewy.semantic import ty
from dewy.semantic.unicode import graphemes


def test_unconstrained_string_checks_do_not_scan_graphemes(monkeypatch):
    def unexpected(_):
        raise AssertionError('a length-free target scanned the literal')
    monkeypatch.setattr(graphemes, 'grapheme_count', unexpected)
    system = ty.TypeSystem()
    literal = ty.StringLiteralType('e\u0301🌱')
    for target in ('string', 'any', ty.StringType(), literal,
                   *(ty.ArrayType(t) for t in ('uint8', 'uint32', 'grapheme', 'char', 'string'))):
        assert system.is_subtype(literal, target)
    assert system.is_subtype(literal, ty.ArrayType('uint8', 7))
    assert system.is_subtype(literal, ty.ArrayType('uint32', 3))
    assert not system.is_subtype(literal, ty.ArrayType('int64'))
    assert not system.is_subtype(literal, 'int64')
    assert not system.is_subtype(literal, ty.StringLiteralType('other'))


@pytest.mark.parametrize('text,scalars,bytes_,clusters', [
    ('', 0, 0, 0), ('\r\n', 2, 2, 1), ('e\u0301🌱', 3, 7, 2), ('👩‍🌾', 3, 11, 1),
])
def test_literal_targets_preserve_their_distinct_length_units(text, scalars, bytes_, clusters):
    system = ty.TypeSystem()
    literal = ty.StringLiteralType(text)
    for element, length in [('uint8', bytes_), ('uint32', scalars),
                            ('grapheme', clusters), ('char', clusters), ('string', clusters)]:
        assert system.is_subtype(literal, ty.ArrayType(element, length))
        assert not system.is_subtype(literal, ty.ArrayType(element, length + 1))
    assert system.is_subtype(literal, ty.StringType(clusters))
    assert not system.is_subtype(literal, ty.StringType(clusters + 1))
    assert system.is_subtype(literal, 'char') == (clusters == 1)
    assert system.is_subtype(literal, 'grapheme') == (clusters == 1)
