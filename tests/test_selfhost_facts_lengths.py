"""Fact lengths and rows (difference rows with their caps, shrunk elements, heap counts, the array-length
ceiling and its strict `$no_assumed_bounds` scopes) agree with frozen Jo: the same proofs, messages and bytes."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_facts_row_queries import chain_program

GLOBS = ('heap_count/*.dewy', 'self_length/*.dewy', 'shrinking/*.dewy', 'pool_fixed_update/*.dewy', 'addr_length/*.dewy',
         'progress_bounded/*.dewy', 'progress_difference/*.dewy', 'parallel_range_bound/*.dewy', 'dogfood34_proofs/*.dewy',
         'loop_bounds/*.dewy', 'facts/*.dewy')


def test_facts_lengths_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [str(p.relative_to(ROOT / 'tests/cases'))[:-5] for g in GLOBS for p in sorted((ROOT / 'tests/cases').glob(g))]
    for n in (8, 40):
        (tmp_path / f'rows{n}.dewy').write_text(chain_program(n))
        cases.append(str(tmp_path / f'rows{n}'))
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) > 100
