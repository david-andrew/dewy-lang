"""Inherited members, receivers, change inference and member closures agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'object/closure_member_escape',
    'frontend/m_records_migrated_records_diagnostics_5',
    'ownership/partial_field_outer_hook_rejected',
    'object/inherited_module',
    'object/closure_member_return',
    'errors/type_of_plain_record',
    'facts/map_entry_method_other_key',
]


def test_dewy_method_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
