"""Loop header widening and stable facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'facts/loop_guard',
    'exact_int/shaped_broadcast',
    'byte_read/proven',
    'notraps24/shape_loop_symbolic',
    'dogfood28_proofs/match_in_loop_keeps_length',
]


def test_facts_loops_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
