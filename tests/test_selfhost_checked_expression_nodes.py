"""Compare checked expression construction, intrinsic registration and narrowing with their Jo twins."""

import pytest

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize(("leaf", "cases"), [
    ("checked_expression_nodes", (
        "broadcast_places/keeps_mutable_record", "default/reference_named",
        "singleton/membership_text_needle", "select_named/captured",
    )),
    ("intrinsic_registration", (
        "set/membership", "set/custom_hash", "conversion/int_boundary_diagnostic",
    )),
    ("path_narrowing", (
        "census_proofs/narrowing_field_named", "census_proofs/narrowing_field_proven",
        "refine_union_storage/union_store_reject",
    )),
    ("type_expression_forms", (
        "type_members/records", "type_members/handles", "type_members/runtime_use",
    )),
], ids=lambda item: item if isinstance(item, str) else None)
def test_checked_expression_twins(compiler, tmp_path, monkeypatch, leaf, cases):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, leaf, cases)
