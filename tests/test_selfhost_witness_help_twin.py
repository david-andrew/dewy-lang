"""Frozen witness diagnostics use the leaf's key and field wording."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_witness_help_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        [
            'dogfood38_proofs/dict_pop_missing_names_default',
            'dogfood38_proofs/record_field_refinement_named',
            'record_field_shape/sibling_written',
        ],
        leaves=('witness_ops',),
    ) == 0
