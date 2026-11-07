"""Reader node builders for tests and expectations, task groups, clamped slices, parallel exits, receivers,
method finishing, constants, integer singletons and target names agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'dogfood/18_roman_tests',
    'frontend/m_directives_direct_directives_identity_1',
    'frontend/m_directives_migrated_directives_diagnostics_5',
    'channels/cancel_blocked',
    'channels/parallel_wait',
    'array/comparison_exact_records',
    'dogfood/104_trie_complete',
    'default_proofs/refuted_literal_union',
    'dogfood/03_config',
]


def test_dewy_node_builds_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
