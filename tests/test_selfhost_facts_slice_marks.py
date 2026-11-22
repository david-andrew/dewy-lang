"""Generation stamps, ordered parents and retained snapshots match frozen Jo."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

LEAF = ('facts_slice_prep',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'facts.jo'
use 'facts_slice_builder.dewy'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
main = ():
    nodes = fill(Node(), 64)
    fact_mark_begin()
    fact_mark_set(5, 2)
    fact_mark_set(5, 7)
    if fact_mark_of(5) != 7 or fact_mark_touched.len() != 1: exit(11)
    parents = FactSliceEdges()
    fact_slice_parent(parents, 5, 9)
    fact_slice_parent(parents, 5, 11)
    if parents.nodes != [9, 11] or parents.next != [-1, 0]: exit(12)
    if fact_mark_parent(5) != 1: exit(13)
    fact_mark_begin()
    if fact_mark_of(5) != 0 or fact_mark_parent(5) != -1 or fact_mark_touched.len() != 0: exit(14)
    fact_mark_touch(5)
    if fact_mark_of(5) != 0 or fact_mark_parent(5) != -1 or fact_mark_touched != [5]: exit(15)
    nodes = fill(Node(), fact_mark_stamp.len() + 1)
    fact_mark_begin()
    if fact_mark_of(5) != 0 or fact_mark_parent(5) != -1: exit(16)
    last = nodes.len() - 1
    fact_mark_set(last, 4)
    if fact_mark_of(last) != 4 or fact_mark_touched != [last]: exit(17)
    fact_slice = FactSlice(flags = [3, 5], base = 8)
    dense = fact_slice
    if fact_slice_flags(7) != 0 or fact_slice_flags(8) != 3 or fact_slice_flags(10) != 0: exit(18)
    fact_slice = FactSlice()
    fact_index_put(fact_slice.flags, 300, 9)
    if fact_slice_flags(300) != 9 or fact_slice_flags(301) != 0 or dense.flags != [3, 5]: exit(19)
    edges = FactSliceEdges()
    fact_slice_edge(edges, 12, 40)
    saved_edges = edges
    fact_slice_edge(edges, 12, 41)
    if saved_edges.nodes != [40] or saved_edges.next != [-1]: exit(24)
    if edges.nodes != [40, 41] or edges.next != [-1, 0] or fact_index_get(edges.heads, 12) != 1: exit(20)
    grown = FactSliceEdges()
    loop i in [0..130): fact_slice_edge(grown, i % 9, i + 100)
    loop i in [0..130):
        prior = if i < 9: -1 else: i - 9
        if grown.nodes[i] != i + 100 or grown.next[i] != prior: exit(25)
    work: int[]
    fact_slice_member(parents, work, 0, 7)
    fact_slice_member(parents, work, 2, 7)
    if work != [2] or fact_mark_parent(2) != 2: exit(21)
    stamps = fact_mark_stamp
    flags = fact_mark_flags
    heads = fact_mark_head
    touched = fact_mark_touched
    fact_mark_set(7, 9)
    fact_slice_parent(parents, 7, 21)
    if stamps[7] == fact_mark_gen or flags[7] != 0 or heads[7] != 0: exit(41)
    if touched == fact_mark_touched: exit(42)
    saved_parents = parents
    fact_slice_parent(parents, 7, 22)
    if saved_parents.nodes.len() + 1 != parents.nodes.len(): exit(43)
    if fact_mark_of(7) != 9 or fact_mark_parent(7) != parents.nodes.len() - 1: exit(44)
    fact_mark_gen = 9223372036854775807
    fact_mark_begin()
    if fact_mark_gen != -9223372036854775807 - 1: exit(45)
    if fact_mark_of(7) != 0 or fact_mark_parent(7) != -1: exit(46)
    fact_mark_set(7, 11)
    fact_mark_set(7, 12)
    if fact_mark_of(7) != 12 or fact_mark_touched != [7]: exit(47)
    print("slice marks ok")
'''


@pytest.mark.parametrize("release", [False, True])
def test_facts_slice_marks_twins(compiler, tmp_path, release):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)
