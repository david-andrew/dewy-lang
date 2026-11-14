"""Prelude bookkeeping (the lazy index and its demanded units, runtime files loaded by name, declaration
order, Dewy prelude modules and their scan, shown paths and splat shadowing) agrees with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'dogfood/128_log_pipeline',
    'dogfood/141_cidr_firewall',
    'dogfood/18_roman_tests',
    'dogfood31_proofs/string_brace_misspelling',
    'overload/unknown_named_argument',
    'time_clock/waits_entry',
    'time_clock/select_timeout_entry',
    'modules/splat_shadows_prelude',
    'settingsplace_rules/pinned',
    'time_resolution/all_and_skip',
    'no_deadlocks/reserve',
    'exact_int/constant_width_checked_named',
    'metatag_prefix/main_setting',
]


def test_prelude_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
