"""Nested optional coalescing selects the same payload type in both builds."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_nested_optional_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        ['coalesce/nested_payload_twin'],
        leaves=('checker_optional',),
    ) == 1
