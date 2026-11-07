"""Cold directive scopes, bundles, panics and version warnings agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'frontend/statements_direct_statements_1',
    'notraps16_fixed/comprehension',
    'match/void_union_trailing_family',
    'no_deadlocks/audited_adapter',
    'queue_cancel_wait/channel_cancel_diag_ok',
    'template_proofs/input_unregistered',
    'directives/forbid_copies_off',
    'effects/no_blocks_io',
]


def test_directive_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
