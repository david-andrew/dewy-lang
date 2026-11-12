"""Tuple writes and nested C callbacks agree with their frozen twins."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_tuple_slot_write_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        ['tuple_slot_write/index_once', 'tuple_slot_write/reachable_position_rejected'],
        leaves=('checker_assigns',),
    ) == 1


def test_nested_ffi_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        [
            'tests/fixtures/ffi_callback_signature/callback_signature_int_reject.dewy',
            'tests/fixtures/ffi_callback_signature/callback_return_string_reject.dewy',
            'tests/fixtures/ffi_callback_signature/callback_return_ptr_int_reject.dewy',
        ],
        leaves=('ffi_checks',),
    ) == 0
