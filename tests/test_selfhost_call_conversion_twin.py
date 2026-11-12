"""Argument scoring agrees for refined literals, call elements and time constants."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_call_conversion_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        [
            'refine_generic_literals/dict_length_generic_arg_ok',
            'refine_generic_literals/dict_length_array_reject',
            'inference/call_into_array',
            'inference/reject_no_context_array',
            'dogfood37_proofs/duration_constant_coerces',
            'dogfood37_proofs/duration_off_grid_rejected',
            'dogfood37_proofs/lambda_for_optional_function',
            'empty_literal/dict_contexts',
            'empty_literal/array_default_wins',
            'refine_generic_mutable/generic_field_ok',
            'refine_generic_mutable/reordered_reject',
        ],
        leaves=('checker_call_convert',),
    ) > 0
