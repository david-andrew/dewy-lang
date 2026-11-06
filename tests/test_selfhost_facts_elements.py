"""Loop element, inventory and fixed comprehension facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'notraps16_endpoints/literal',
    'effects/fixed_comprehension_short',
    'range/stepped_error_10',
    'spread/call_context',
    'dogfood24_proofs/field_keys_counted',
    'dogfood29_proofs/optional_best_helper',
    'notraps16_fixed/branch',
]


def test_facts_elements_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
