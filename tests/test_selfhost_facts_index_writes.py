"""Fact index writers and value transitions (open-address insertion and growth, value slots and their
hashed-index promotion, projection and row insertion past the scan limits, new values, constants,
bindings, rebinding, bounds and reindexing) agree with frozen Jo: the same proofs, diagnostics and
bytes over small and large states."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_facts_projection_queries import record_program
from tests.test_selfhost_facts_row_queries import chain_program

GLOBS = ('facts/*.dewy', 'loop_bounds/*.dewy', 'saved_operands/*.dewy', 'dict_refine/*.dewy', 'refine_proven_rows/*.dewy',
         'heap_count/*.dewy', 'queue_refined_slots/*.dewy', 'witness_bounds/*.dewy', 'dict_sibling/*.dewy')


def test_facts_index_writes_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [str(p.relative_to(ROOT / 'tests/cases'))[:-5] for g in GLOBS for p in sorted((ROOT / 'tests/cases').glob(g))]
    for n in (31, 32, 33, 70, 140):
        (tmp_path / f'rows{n}.dewy').write_text(chain_program(n))
        (tmp_path / f'records{n}.dewy').write_text(record_program(n))
        cases += [str(tmp_path / f'rows{n}'), str(tmp_path / f'records{n}')]
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) > 100
