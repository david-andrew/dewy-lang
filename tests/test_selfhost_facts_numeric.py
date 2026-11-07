"""Scaled products, quotients, midpoints, bit operations, extrema, rationals and powers agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'exact_int/constant_width',
    'notraps17_word/halves',
    'operators/prefix_tilde',
    'channels/cancel_blocked',
    'exact_int/shaped_broadcast',
    'dogfood31_proofs/inline_index_after_guards',
    'notraps24/either_power',
    'exact_int/constant_width_reject_divide',
    'notraps17_word/small_destination',
    'object/static_reads',
]


def test_facts_numeric_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
