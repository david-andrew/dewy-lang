"""The checked evaluator's host adapters (constant initializers, wrapping conversions, byte cuts,
literals made from values, running an expression) as a Dewy leaf agree with frozen Jo: the same
messages, exit codes and bytes for programs evaluated while checking."""
from pathlib import Path

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'tests/cases/comptime').glob('*.dewy')) + [
    'tests/cases/constant/typed_integer_context.dewy', 'tests/cases/members_nonliteral/binary.dewy',
    'tests/cases/literal_subset_bindings/subsets.dewy', 'tests/cases/dogfood/122_roman_numerals.dewy',
    'tests/cases/dogfood/141_cidr_firewall.dewy', 'tests/cases/time/core_arithmetic.dewy']


def test_comptime_ops_match_twin(compiler, tmp_path, monkeypatch):
    results = compare_builds(compiler, tmp_path, monkeypatch, ('comptime_ops',), CASES)
    assert any(r[2] == 0 for r in results) and any(r[2] != 0 for r in results)
