"""Large binding ids must not alias unrelated evidence in the proof engine."""

import pytest

from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir
from dewy.semantic.analyze import bounds as b


@pytest.mark.parametrize('large', [2**20 - 1, 2**20, 2**21, 2**42, 2**80])
def test_fact_identity_and_transfers(large):
    span = Span(0, 0)
    validator = b._BoundsValidator(bindings.BindingRegistry(), SrcFile(None, ''), hir.Block(span, 'void', [], True))
    length = b._length_key(large)
    keys = [large, length, b._index_fact_key(1, large), b._index_fact_key(large, 1),
            b._nonzero_key(1), b._nonzero_key(large), b._order_key(1, large),
            b._order_key(1, length), b._order_key(large, 1),
            b._remainder_key(1, length, large), b._remainder_key(large, length, 1)]
    assert len(set(keys)) == len(keys)
    assert b._is_length_key(length)
    assert not any(b._is_length_key(key) for key in keys if key != length)
    assert b._decode_index_fact(keys[2]) == (1, large)
    assert b._decode_order_fact(keys[7]) == (1, length)
    assert b._decode_remainder_fact(keys[9]) == (1, length, large)

    state = {key: b.Interval(i, None) for i, key in enumerate(keys)}
    extracted = validator._facts_of(state, 1)
    assert b._index_fact_key(0, large) in extracted
    assert b._nonzero_key(0) in extracted
    assert validator._rekey(b._nonzero_key(0), large) == b._nonzero_key(large)
    forgotten = dict(state)
    b._drop_index_facts(forgotten, array_id=large)
    assert b._index_fact_key(1, large) not in forgotten
    assert b._nonzero_key(1) in forgotten
    assert b._index_fact_key(large, 1) in forgotten
    assert b._order_key(1, large) in forgotten
    assert b._order_key(1, length) not in forgotten
    assert b._remainder_key(1, length, large) not in forgotten
    assert validator._join_states([state, state]) == state


@pytest.mark.parametrize('large', [2**20, 2**21, 2**42, 2**80])
def test_relation_does_not_prove_a_different_large_binding(large):
    span = Span(0, 0)
    validator = b._BoundsValidator(bindings.BindingRegistry(), SrcFile(None, ''), hir.Block(span, 'void', [], True))
    state = {b._order_key(1, large): b.Interval(1, None)}
    assert validator._ordered(1, large, 1, state)
    assert not validator._ordered(1, b._length_key(large), 1, state)
    assert not validator._ordered(large, 1, 1, state)
    # These two index facts collided when ids were packed into twenty bits.
    assert b._index_fact_key(1, large + 2**20) != b._index_fact_key(2, large)
