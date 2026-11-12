"""Ordered range construction and membership match their frozen twins."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_ordered_range_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        ['range/ordered_text_twin', 'dogfood37_proofs/date_range_loop_named'],
        leaves=('checker_call_services', 'checker_expr'),
    ) == 2
