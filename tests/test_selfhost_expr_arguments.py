"""Exercise expression arguments, call spelling and literal representations with both compilers."""

import pytest

from tests.selfhost_build_double import compare_builds, compare_golden_cases
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize(("leaf", "cases"), [
    ("index_operand_checks", ("addr_length/negative_index", "end/index_slices", "array/get_int_index")),
    ("mutable_argument_routes", ("argument/mutable_disjoint", "argument/mutable_callable_overlap",
                                 "argument/mutable_borrowed_global", "argument/mutable_borrowed_params")),
    ("literal_number_forms", ("rational/word", "rational/word_narrowing", "rational/division_float",
                              "rational/decimal_text_exact", "rational/comprehension_decimal_array")),
    ("default_arguments", ("default/reference_named", "default/reference_nested", "default/reference_chain",
                           "default/reference_closure", "default/reference_loop_shadow", "default/reference_mutable")),
    ("type_expression_forms", ("json/typed_map", "record/bare_defaults", "record/bare_required",
                               "callable/return_handle", "style/zero_argument_calls")),
    ("overload_diagnostics", ("partial/ambiguous_overload", "partial/ambiguous_overload_annotated",
                              "overload/group_unsigned_literal", "overload/group_types")),
    ("call_style_lookup", ("style/zero_argument_calls", "record/function_field_shadowed", "partial/method_handle",
                           "overload/user_shadows_prelude")),
], ids=lambda arg: arg if isinstance(arg, str) else None)
def test_expr_argument_twins(compiler, tmp_path, monkeypatch, leaf, cases):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases)


def test_character_literals_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    program = tmp_path / "characters.jo"
    program.write_text('''main = ():
    a: int = "A"
    b: int = "é"
    c: int = "猫"
    d: int = "🦊"
    print(a, b, c, d)
''')
    invalid = tmp_path / "multiple.jo"
    invalid.write_text('main = ():\n    x: int = "ab"\n    print(x)\n')
    good, bad = compare_builds(compiler, tmp_path, monkeypatch, ("character_literals",), (program, invalid))
    assert good[2] == 0 and bad[2] != 0
