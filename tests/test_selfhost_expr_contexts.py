"""Exercise the same expression contexts through the Dewy checker and its frozen leaves."""

import pytest

from tests.selfhost_build_double import compare_builds, compare_golden_cases
from tests.support import compiler  # noqa: F401
from tests.test_dewy_data_after_move import MOVED, TAKEN_FIRST

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize(("leaf", "cases"), [
    ("aggregate_sources", ("fixed/array_error_1", "fixed/array_dictionary", "spread/arrays",
                           "spread/call_context", "spread/managed_values")),
    ("call_lookup_context", ("mod_call/range", "generic/constructor_imported", "generic/structural_result")),
    ("call_shape_queries", ("style/zero_argument_calls", "record/function_field_shadowed", "match/copy")),
    ("call_wait_inference", ("generic/array_literal_deferred_float", "generic/constructor_callbacks",
                             "generic/constructor_conflicting_elements", "generic/array_literal_empty_specific")),
    ("failure_coalescing", ("coalesce/listed_not_exception", "coalesce/listed_not_held", "coalesce/listed_kinds",
                            "coalesce/expected_union", "explicit_cancellation/coalesce")),
    ("path_narrowing", ("census_proofs/narrowing_field_proven", "census_proofs/narrowing_field_named",
                        "optional/fill_join", "match/family_parent_arm")),
    ("map_entry_places", ("fixed/array_dictionary", "json/typed_map", "empty_literal/dict_contexts")),
    ("type_expression_forms", ("json/typed_map", "json/typed_nested", "json/typed_integer_keys")),
], ids=lambda arg: arg if isinstance(arg, str) else None)
def test_expr_context_twins(compiler, tmp_path, monkeypatch, leaf, cases):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases)


def test_moved_argument_data_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    moved = tmp_path / "moved.jo"
    moved.write_text(MOVED)
    first = tmp_path / "first.jo"
    first.write_text(TAKEN_FIRST)
    bad, good = compare_builds(compiler, tmp_path, monkeypatch, ("moved_argument_data",), (moved, first))
    assert good[2] == 0 and bad[2] != 0
    assert "data(cell) reads 'cell' after it was moved" in bad[4]


def test_game_call_checks_habit_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    bad = tmp_path / "shape.dewy"
    bad.write_text("main=()=>{line(1 2 3 4)}\n")
    own = tmp_path / "own.dewy"
    own.write_text("line=(a:int b:int c:int d:int)=>a+b+c+d\nmain=()=>printl(line(1 2 3 4))\n")
    rejected, accepted = compare_builds(compiler, tmp_path, monkeypatch, ("game_call_checks",), (bad, own))
    assert rejected[2] != 0 and accepted[2] == 0
    assert "line takes two points" in rejected[4]


def test_time_rule_packs_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    (tmp_path / "bad.bin").write_bytes(b"DZP")
    paths = []
    for name in ("bad", "missing"):
        source = tmp_path / f"{name}.dewy"
        source.write_text(f"$time.rules='{name}.bin'\nprintl(zone\"UTC\")\n")
        paths.append(source)
    bad, missing = compare_builds(compiler, tmp_path, monkeypatch, ("time_rule_packs",), paths)
    assert bad[2] != 0 and "is not a rule pack" in bad[4]
    assert missing[2] != 0 and "cannot read" in missing[4]
