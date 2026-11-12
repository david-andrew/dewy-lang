"""A local variable shadowing a unit gets the same product diagnostic."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_hidden_unit_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        ['messages1107/local_hides_unit'],
        leaves=('unit_rare',),
    ) == 0
