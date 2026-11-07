"""Member services, numeric bounds and field services agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'multi/written_mixed_types_hint',
    'refine_alias_tags/element_nested_field',
    'precision_inference/members_comptime',
    'dictionary/totaldict_pop',
    'no_deadlocks/poll',
    'object/inherited_module',
    'object/method_value',
    'comptime/runtime_field',
    'copies/member_precedence',
    'float_guards/field_guard',
    'record/function_field_shadowed',
    'misc/main_float_result',
    'dictionary/totaldict_partial',
    'comptime/reject_library_text',
    'float_constants/reject_unknown_limit',
    'handle/closure_needs_arguments',
    'printl("{int8.min} {int8.max} {int16.min} {uint16.max} {int32.min} {uint32.max} {int64.min} {int64.max} {uint64.max}")\n',
]


def test_checks_member_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
