"""Scalar, literal and membership value construction agree with frozen Jo.

Exercise projection reuse and growth, branch snapshots, element hulls and
constructor fields, signed/unsigned literals, exact capture hooks and text-set
membership. The recursive transfer and memo storage are real shared services.
"""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_facts_projection_queries import record_program

GLOBS = (
    'facts/*.dewy', 'uint64_ceiling/*.dewy', 'self_length/*.dewy',
    'singleton/string_set*.dewy', 'set/string_set*.dewy',
    'refine_proven_rows/*.dewy', 'refine_length_helpers/*.dewy',
    'pool_fixed_update/*.dewy', 'effects/power_exponent*.dewy', 'notraps24/*power*.dewy',
)


def test_facts_values_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in GLOBS for p in (ROOT / 'tests/cases').glob(glob)})
    for n in (4, 31, 40, 70):
        source = tmp_path / f'projection{n}.dewy'
        source.write_text(record_program(n))
        cases.append(str(source.with_suffix('')))
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=('facts_values',)) > 70
