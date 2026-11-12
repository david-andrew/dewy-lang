"""Decimal quantity bindings and later float writes agree across compiler builds."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_decimal_unit_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        [
            'dogfood37_proofs/decimal_unit_turns_float',
            'dogfood37_proofs/decimal_unit_stays_float_rejected',
        ],
        leaves=('checker_hooks', 'checker_vardecls'),
    ) == 1
