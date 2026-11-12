"""Nested push counts and literal dictionary key bounds agree with frozen twins."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_nested_push_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'dict_key_nonempty/built',
        'dict_key_nonempty/built_int',
        'dict_key_nonempty/changed_rejected',
        'dict_key_nonempty/lower_bound_is_not_exact_rejected',
        'dict_key_nonempty/unsupported_source_keeps_facts',
    ]) > 0


def test_literal_key_bounds_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'dict_key_nonempty/literal',
        'dict_key_nonempty/duplicates',
        'dict_key_nonempty/empty_rejected',
        'dict_key_nonempty/empty_spread_rejected',
    ]) > 0
