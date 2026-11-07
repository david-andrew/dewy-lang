"""Range calls, steps, exhaustion, narrowing and counted loops agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'constant/view_write_after',
    'effects/refined_param_proven',
    'facts/selection_specialized_identity',
    'conversion/wrap_transmute',
    'facts/selection_loop_resize',
    'effects/refined_param_unproved',
    'notraps17_word/unbounded',
]


def test_facts_ranges_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
