"""Fact value lookups (the open-address index, value slots by hint, index or binary search, bounds,
bindings, truth and signed bounds) agree with frozen Jo over states small and large."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_facts_projection_queries import record_program
from tests.test_selfhost_facts_row_queries import chain_program

GLOBS = ('facts/*.dewy', 'loop_bounds/*.dewy', 'saved_operands/*.dewy', 'uint64_ceiling/*.dewy', 'dict_refine/*.dewy',
         'refinements/*.dewy', 'heap_count/*.dewy', 'witness_bounds/*.dewy')


def test_facts_value_queries_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [str(p.relative_to(ROOT / 'tests/cases'))[:-5] for g in GLOBS for p in sorted((ROOT / 'tests/cases').glob(g))]
    for n in (31, 70):
        (tmp_path / f'rows{n}.dewy').write_text(chain_program(n))
        (tmp_path / f'records{n}.dewy').write_text(record_program(n))
        cases += [str(tmp_path / f'rows{n}'), str(tmp_path / f'records{n}')]
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) > 100
