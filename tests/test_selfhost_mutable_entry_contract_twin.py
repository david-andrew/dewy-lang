"""By-value contract checks use the same mutable argument projection."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_mutable_entry_contract_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        [
            'mutable_entry_contract/accepted',
            'mutable_entry_contract/after_helper',
            'mutable_entry_contract/checked_at_run_time',
            'mutable_entry_contract/handle_at_run_time',
        ],
        leaves=('lower_group',),
    ) > 0
