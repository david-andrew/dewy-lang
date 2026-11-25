"""Final compiler behavior with the member_checked leaf and with its frozen twin."""

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_member_checked_twins(compiler, tmp_path, monkeypatch):
    compare_golden_cases(compiler, tmp_path, monkeypatch, "member_checked", (
        "member_template/comptime_members",
        "type_members/records",
        "type_members/runtime_use",
        "type_members/named_twice",
    ), flags=((), ("--release",)))
