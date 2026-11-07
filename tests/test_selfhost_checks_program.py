"""Program-level name, callback, test and game checks agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'main/explicit_call_rejected',
    'unpack/nested_scalar',
    'draw_context/user_called_draw',
    'misc/proof_directive',
    'unpack/leaf_discard_incompatible',
    'draw_context/draw_value',
]


def test_checks_program_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
