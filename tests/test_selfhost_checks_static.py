"""Static truth of assertions and the build block agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'main/explicit_call_rejected',
    'frontend/migrated_direct_migrated_identity_1',
    'comptime/reject_library_text',
    'testing/expect_returns',
    'misc/proof_directive',
    'facts/join_one_sided',
    'facts/write_after_guard',
]


def test_checks_static_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
