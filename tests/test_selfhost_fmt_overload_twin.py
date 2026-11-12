"""Constant format checks select the same overload in both compilers."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_fmt_overload_twin(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        [
            'fmt/patterns', 'fmt/integer_takes_no_float', 'fmt/number_takes_no_text',
            'inference/expected_literal', 'inference/reject_expected_literal',
        ],
        leaves=('checker_call_resolve',),
    ) > 0
