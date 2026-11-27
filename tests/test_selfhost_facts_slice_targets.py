"""Slice edge construction and target routes agree with frozen Jo."""
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

LEAF = ('facts_slice_prep',)

EDGES = '''use 'main.jo'
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
    if fact_mark_of(5) != 7: exit(11)
    parents = FactSliceEdges()
    fact_slice_parent(parents, 5, 9)
    fact_slice_parent(parents, 5, 11)
    if parents.nodes != [9, 11] or parents.next != [-1, 0]: exit(12)
    if fact_mark_parent(5) != 1: exit(13)
    fact_mark_begin()
    if fact_mark_of(5) != 0 or fact_mark_parent(5) != -1: exit(14)
    fact_mark_touch(5)
    if fact_mark_of(5) != 0 or fact_mark_parent(5) != -1: exit(15)
    nodes = fill(Node(), 2500)
    fact_mark_begin()
    if fact_mark_of(5) != 0 or fact_mark_parent(5) != -1: exit(16)
    last = nodes.len() - 1
    fact_mark_set(last, 4)
    if fact_mark_of(last) != 4: exit(17)
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
    print("slice scratch ok")
'''


def test_facts_slice_prep_edges_twins(compiler, tmp_path):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, False, EDGES, extra_stems=LEAF, jo_doubles=modules)

TARGETS = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'facts.jo'
use 'facts_slice_builder.dewy'
use 'facts_value_queries.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'refinement_types.dewy'
use 'refine.jo'
use 'places.jo'
use 'types.jo'
main = ():
    nodes = fill(Node(), 128)
    locals = fill(Local(), 4)
    locals[1] = Local(owner = 7)
    nodes[1] = Node(kind = .ident, aux = i32(int(SK.local)), sym = 1)
    nodes[2] = Node(kind = .field, a = 1)
    nodes[3] = Node(kind = .index, a = 2)
    nodes[4] = Node(kind = .addr, a = 3)
    nodes[5] = Node(kind = .unwrap, a = 4)
    p = fact_slice_root(5)
    if p.declaration != 1 or p.owner != 7: exit(31)
    locals[2] = Local(owner = 8, flags = i32(LF_ALIAS), alias = 5)
    nodes[6] = Node(kind = .ident, aux = i32(int(SK.local)), sym = 2)
    if fact_slice_root(6).declaration != 1: exit(32)
    place_locked[2] = true
    if fact_slice_root(6).declaration != 2: exit(33)
    place_locked = {}
    loop i in [20..90): nodes[i] = Node(kind = .field, a = i32(i + 1))
    nodes[90] = nodes[1]
    if fact_slice_root(20).declaration != 0 or fact_slice_root(27).declaration != 1: exit(34)
    lists = [5, 6, 5]
    nodes[10] = Node(kind = .tuple, list = 0, nlist = 3)
    writers = FactSliceEdges()
    fact_slice_target(writers, 10, 99)
    if writers.nodes != [99, 99, 99] or writers.next != [-1, 0, 1]: exit(35)
    if fact_index_get(writers.heads, fact_root_key(p)) != 2: exit(36)
    fact_slice_writer(writers, PlaceIdentity(), 100)
    if writers.nodes.len() != 3: exit(37)
    types = fill(TypeInfo(), 4)
    types[1] = TypeInfo(kind = .fn_, mutmask = 5)
    nodes[7] = Node(kind = .ident, type = 1)
    nodes[8] = Node(kind = .call, aux = 1, a = 7, list = 0, nlist = 3)
    writers = FactSliceEdges()
    fact_slice_place_arguments(writers, 8)
    if writers.nodes != [8, 8] or writers.next != [-1, 0]: exit(38)
    lists = [5, 6, 1]
    values = [111]
    nodes[5].aux2 = 2
    types[2] = TypeInfo(kind = .refined, st = 1)
    a = RefTerm(kind = 2, value = 0)
    b = RefTerm(kind = 5, value = 2)
    ref_predicates = [[], [RefAtom(.le, a, b), RefAtom(.le, RefTerm(kind = 2, value = -1), RefTerm(kind = 5, value = 3)), RefAtom(.le, b, a)]]
    fact_slice_contract_actuals(8, 5, values)
    if values != [111, 5, 5, 1, 1, 5]: exit(39)
    nodes[5].aux2 = 3
    fact_slice_contract_actuals(8, 5, values)
    if values != [111, 5, 5, 1, 1, 5, 5, 8]: exit(40)
    print("slice targets ok")
'''


def test_facts_slice_prep_targets_twins(compiler, tmp_path):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, False, TARGETS, extra_stems=LEAF, jo_doubles=modules)
