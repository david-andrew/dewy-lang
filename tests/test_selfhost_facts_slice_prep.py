"""Slice child enumeration preserves masks, order, COW and real proof output."""
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_facts_projection_queries import record_program
import pytest

pytestmark = pytest.mark.nightly

LEAF = ('facts_slice_prep',)
GLOBS = ('facts/*.dewy', 'loop_bounds/*.dewy', 'saved_operands/*.dewy',
         'refine_proven_rows/*.dewy', 'refine_length_helpers/*.dewy',
         'witness_bounds/*.dewy', 'parallel_range_bound/*.dewy',
         'addr_length/*.dewy', 'coverlib_proofs/*.dewy')

CHILDREN = """use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
main = ():
    nodes = fill(Node(), 10)
    lists = [7, 8, 7]
    nodes[1] = Node(kind = .arm, a = 2, b = 3, c = 4, list = 0, nlist = 3)
    expected = [2, 3, 4, 7, 8, 7]
    if fact_slice_children(1) != expected: exit(11)
    children = [99]
    snapshot = children
    fact_slice_push_children(children, 1)
    if children != [99, 2, 3, 4, 7, 8, 7] or snapshot != [99]: exit(12)
    nodes[1] = Node(kind = .lambda, a = 2, b = 3, c = 4, list = 0, nlist = 3)
    if fact_slice_children(1) != []: exit(13)
    fact_slice_push_children(children, 1)
    if children != [99, 2, 3, 4, 7, 8, 7]: exit(14)
    nodes[1] = Node(kind = .nil)
    if fact_slice_children(1) != []: exit(15)
    nodes[1] = Node(kind = .for_, a = 2, b = 3, c = 9, d = 8)
    if fact_slice_children(1) != [2, 3]: exit(16)
    nodes = fill(Node(), 4096)
    nodes[4095] = Node(kind = .array, b = 3, list = 0, nlist = 3)
    if fact_slice_children(4095) != [3, 7, 8, 7]: exit(17)
    print("slice children ok")
"""


def test_facts_slice_prep_children_twins(compiler, tmp_path):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, False, CHILDREN, extra_stems=LEAF, jo_doubles=modules)


def test_facts_slice_prep_program_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in GLOBS for p in (ROOT / 'tests/cases').glob(glob)})
    for n in (4, 40, 140):
        source = tmp_path / f'slice{n}.dewy'
        source.write_text(record_program(n))
        cases.append(str(source.with_suffix('')))
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) > 100
