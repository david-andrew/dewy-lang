"""A passed constant check removes the same panic in both compiler builds."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_constant_check_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        ['melody_check/literal_needs_no_opt_in', 'melody_check/computed_text_needs_opt_in'],
        leaves=('constant_checks', 'panic_inventory'),
    ) == 1
