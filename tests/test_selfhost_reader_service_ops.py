"""The forwarding services behind the reader host record agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'frontend/m_directives_direct_directives_identity_1',
    'arena/strict_capacity',
    'deadlock/recursive_service',
    'ffi/ptr_string_bytes_to_c',
    'ownership/tuple_unpack',
    'object/inherited_module',
    'frontend/m_tasks_direct_tasks_identity_1',
    'frontend/m_directives_migrated_directives_diagnostics_9',
    'frontend/m_statements_direct_statements_identity_1',
    'frontend/m_forms_direct_forms_identity_1',
    'ffi/intrinsic',
    'effects/no_blocks_row',
    'notraps17_keys/event',
    'transfer/claim_row',
    'frontend/m_records_migrated_records_diagnostics_11',
    'frontend/direct_direct_expression_diagnostics_3',
    'end/reserved_unpack',
    'frontend/m_statements_migrated_statements_diagnostics_6',
    'witness/proof_exit',
    'queue_send_requirement/mpmc_payload_send_reject',
    'notraps16_endpoints/too_small',
]


def test_reader_service_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
