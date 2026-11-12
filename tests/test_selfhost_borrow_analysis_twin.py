"""Borrow snapshots across read-only calls lower alike in both compilers."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_borrow_analysis_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        [
            'argument/mutable_param_entry_library_calls',
            'argument/mutable_borrowed_params',
            'argument/borrow_later_write',
        ],
        leaves=('lower_analysis',),
    ) > 0
