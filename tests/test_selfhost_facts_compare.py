"""Recursive comparison/assumption agrees with frozen Jo, including bounded graph searches,
open endpoints, affine/product proofs, captured booleans and state snapshots in both build modes."""
import pytest

from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_facts_row_queries import chain_program

GLOBS = ('facts/affine*.dewy', 'facts/nonlinear*.dewy', 'facts/comparison.dewy',
         'facts/bounded_sum*.dewy', 'facts/endpoint*.dewy', 'facts/shape_guard*.dewy',
         'facts/snapshot*.dewy', 'facts/loop_snapshot.dewy', 'facts/short_circuit.dewy',
         'facts/runtime_or.dewy', 'facts/plain_binding_guards.dewy',
         'facts/repeated_array_endpoints*.dewy', 'facts/narrowed*.dewy',
         'facts/write_after_guard.dewy', 'facts/uint64_range*.dewy', 'facts/wrap_unknown.dewy',
         'facts/budget.dewy', 'saved_operands/*.dewy', 'product_bounds/*.dewy',
         'dogfood35_proofs/*.dewy', 'loop_bounds/*.dewy')


@pytest.mark.parametrize('flags', [(), ('--release',)])
def test_facts_compare_twins(compiler, tmp_path, monkeypatch, flags):  # noqa: F811
    cases = [str(p.relative_to(ROOT / 'tests/cases'))[:-5]
             for g in GLOBS for p in sorted((ROOT / 'tests/cases').glob(g))]
    for n in (8, 31, 40, 70):
        (tmp_path / f'chain{n}.dewy').write_text(chain_program(n))
        cases.append(str(tmp_path / f'chain{n}'))
    # Rejected programs are part of this boundary: compare their diagnostics and statuses too.
    compare_facts(compiler, tmp_path, monkeypatch, cases, flags)
