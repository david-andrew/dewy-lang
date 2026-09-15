"""A positive meet keeps predicates when the compatible base gets narrower."""
import pytest

from dewy.semantic import ty


@pytest.mark.parametrize('reverse', [False, True])
def test_refined_word_and_literal_overlap(reverse):
    word = ty.RefinedType('int64', (ty.Proposition('self', '>=?', -1),
                                   ty.Proposition('self', '<=?', 1)))
    singleton = ty.IntegerLiteralType(-1)
    system = ty.TypeSystem()
    pair = (singleton, word) if reverse else (word, singleton)
    assert not system.is_empty(ty.intersect(*pair))
    assert system.is_empty(ty.intersect(word, 'string'))
    assert system.is_subtype(ty.intersect(*pair), singleton)


def test_refined_array_and_exact_length_keep_the_length_promise():
    sequence = ty.RefinedType(ty.ArrayType('int64'), (ty.Proposition('length', '>=?', 2),))
    exact = ty.ArrayType('int64', 3)
    system = ty.TypeSystem()
    assert not system.is_empty(ty.intersect(sequence, exact))
    assert system.is_subtype(ty.intersect(sequence, exact), exact)
