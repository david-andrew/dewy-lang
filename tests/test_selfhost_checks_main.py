"""Main's result, error kinds and exit codes agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'main/exit_code_member_cap',
    'main/exit_codes_over_cap_rejected',
    'main/exit_code_member',
    'main/int_result_rejected',
    'main/exit_code_written_zero',
    'queues/spsc_wait_certificate',
    'frontend/declarations_declaration_fallback_6',
]


def test_checks_main_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
