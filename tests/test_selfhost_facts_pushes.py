"""Loop push, count and carried facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'notraps16_fixed/comprehension',
    'dogfood13_proofs/matching_rows',
    'effects/mixed_width_counter',
    'comprehension/reserved_control_fallback',
    'dogfood22_proofs/dp_table_rows',
    'dogfood21_proofs/array_reader_keeps_roots',
    'dogfood20_proofs/const_table_keys',
]


def test_facts_pushes_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
