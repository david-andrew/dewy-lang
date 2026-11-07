"""Cast, collection, place, variant and type-application services agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'dictionary/totaldict_pop',
    'secret/leak_cast',
    'frontend/strings_string_diagnostics_4',
    'generic/value_conflicting_type',
    'object/print_record_order',
    'surface/dictionary_name_key',
    'coalesce/nonoptional',
    'melody_check/reject_bad_letter_loop',
    'refinements/string_alias_conversion_refuted',
    'byte_slice/unproven_boundary',
    'match/refined_offset_gap',
    'format/type_spelling',
    'dictionary/float_key_proven',
    'dictionary/totaldict_partial',
    'refinements/alias_conversion_refuted',
    'generic/value_wrong_type_count',
    'default/field_later',
    'errors/optional_union_cast_hint',
    'handle/closure_needs_arguments',
]


def test_checks_cast_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
