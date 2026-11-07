"""Name reads and unknown-name errors agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'multi/written_mixed_types_hint',
    'units/dimensioned_power',
    'import_cycles/use_before_init_one_file',
    'missing/name',
    'no_deadlocks/handler_not_send',
    'constant/view_write_loop',
    'decimal/global_writers',
    'misc/main_float_result',
    'units/mismatch_compare',
    'errors/unit_import_hint',
    'dogfood31_proofs/string_brace_misspelling',
    'float_constants/reject_old_inf',
    'float_constants/reject_old_nan',
    'jo:main = ():\n    print("<{tag}>")\n',
]


def test_checks_ident_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
