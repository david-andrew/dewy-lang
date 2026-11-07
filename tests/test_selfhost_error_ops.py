"""Nominal families, inferred throws, propagation and forwarding agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'refine_alias_tags/element_nested_field',
    'queues/spsc_wait_certificate',
    'notraps17_keys/current_contract',
    'errors/forward_method_call',
    'queues/unsent_family_concrete',
    'errors/family_pattern_join',
    'frontend/strings_string_diagnostics_4',
    'deadlock/channel_self',
    'notraps17_keys/method',
    'errors/or_throw_optional_error',
    'dogfood36_proofs/or_throw_names_every_alternative_rejected',
    'input_failure/reject_unhandled_or_throw',
]


def test_error_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
