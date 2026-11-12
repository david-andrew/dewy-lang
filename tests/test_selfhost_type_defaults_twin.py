"""Type parameter defaults resolve alike in the leaf and frozen twin."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_type_defaults_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        ['generic/type_defaults', 'dogfood37_proofs/quantize_instant_utc_minute'],
        leaves=('checker_resolve',),
    ) > 0
