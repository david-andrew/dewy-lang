"""Projection identity, ordered construction, caps and snapshots match frozen Jo."""
import pytest
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAF = ('facts_values',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'effect_types.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'facts.jo'
use 'facts_slice_builder.dewy'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
use 'facts_projection_queries.dewy'
use 'facts_compare.dewy'
use 'facts_plans.dewy'
use 'facts_lengths.dewy'
use 'refine.jo'
use 'refinement_types.dewy'
use 'util.jo'
fail = (code: int):
    print("assertion {code}")
    exit(code)
plain_ids = (values: int[]) -> int: values[0]
main = ():
    init_types()
    nodes = fill(Node(), 16); locals = fill(Local(), 8)
    # Fixed expected encodings cover all root tags and word/mask boundaries.
    roots = [PlaceRoot.local, PlaceRoot.global, PlaceRoot.formal, PlaceRoot.capture, PlaceRoot.resource]
    loop i in [0..roots.len()):
        p = PlaceIdentity(roots[i], 91, 1, 7, .field, 8)
        if fact_root_key(p) != 8 + i: fail(10)
    if fact_root_key(PlaceIdentity(.resource, 0, -1)) != -4: fail(11)
    if fact_root_key(PlaceIdentity(.global, 0, 1 << 61)) != 1: fail(12)
    if fact_pair_key(1, 2) != 4294967298 or fact_pair_key(-1, 0) != -4294967296: fail(13)
    if fact_pair_key(0, FACT_MIN) != FACT_MIN or fact_pair_key(4294967296, 3) != 3: fail(14)
    if fact_projection_key(1, -1, false) != 12884901887 or fact_projection_key(1, -1, true) != 17179869183: fail(15)
    if fact_projection_key(-1, 0, false) != -8589934592 or fact_projection_key(1 << 31, 0, false) != 0 or fact_projection_key(0, 4294967296, false) != 0: fail(16)
    locals[1] = Local(owner=9, type=i32(T_INT))
    nodes[1] = Node(kind=.ident, sym=1, aux=1); nodes[2] = Node(kind=.addr, a=1)
    nodes[3] = Node(kind=.ident, sym=3, aux=2); nodes[4] = Node(kind=.int_lit)
    if fact_place(0).declaration != 0 or fact_place(4).declaration != 0: fail(17)
    p = fact_place(2)
    if p.root != .local or p.owner != 9 or p.declaration != 1: fail(18)
    p = fact_place(3)
    if p.root != .global or p.owner != 0 or p.declaration != 3: fail(19)
    fact_terms = [FactTerm()]; fact_query = false; fact_owner = 1; fact_hull_owner = -1
    refine_active = false; fact_constructor_actuals.clear()
    arr = mk_array(T_INT); row_type = mk_array(T_I8)
    s = FactState()
    fresh = fact_project(s, 0, 7, false, T_I8)
    if fact_bound(s, fresh).lo != -128 or fact_bound(s, fresh).hi != 127 or s.projections.len() != 0: fail(20)
    base = fact_new(s, FactBound(), FactTerm(type=arr)); saved = s
    field = fact_project(s, base, 17, false, T_INT); count = s.ids.len()
    if fact_project(s, base, 17, false, T_INT) != field or s.ids.len() != count or saved.projections.len() != 0: fail(21)
    # A Jo collection must infer the original plain-word result type.
    if plain_ids([field]) != field: fail(27)
    length = fact_project(s, base, -1, false, T_INT)
    if fact_bound(s, length).lo != 0 or fact_bound(s, length).hi != fact_length_max(): fail(22)
    # Equivalent captured indexes find the first existing element, including
    # after index promotion. A uniform copy is only the later fallback.
    a = fact_constant(s, 7); b = fact_constant(s, 7)
    value = fact_constant(s, 42)
    fact_add_projection(s, FactProjection(base, a, true, value))
    copy = fact_constant(s, 99)
    fact_add_projection(s, FactProjection(base, FACT_ELEMENT_COPY, false, copy))
    if fact_project(s, base, b, true, T_INT) != value: fail(23)
    other = fact_constant(s, 8)
    if fact_project(s, base, other, true, T_INT) != copy: fail(24)
    before = s
    loop i in [0..40): fact_project(s, base, 100 + i, false, T_INT)
    if not fact_projections_indexed(s) or before.projections.len() >= s.projections.len() or fact_project(s, base, b, true, T_INT) != value: fail(25)
    # Literal text identity does not publish a generic projection.
    nodes[5] = Node(kind=.str_lit, sval=123, aux=0)
    text = fact_new(s, FactBound(), FactTerm(origin=5, type=T_STR)); count = s.projections.len()
    identity = fact_project(s, text, FACT_TEXT_ID, false, T_INT)
    if fact_bound(s, identity).lo != 123 or fact_bound(s, identity).hi != 123 or s.projections.len() != count: fail(26)
    # Hull and strict-below transfers retain their ordered witness rows.
    h = FactState(); fact_hull_owner = fact_owner
    hb = fact_new(h, FactBound(), FactTerm(type=row_type))
    hv = fact_new(h, FactBound(-10, 20, true)); hi = fact_constant(h, 50)
    fact_add_projection(h, FactProjection(hb, FACT_ELEMENT_VALUE, false, hv))
    fact_add_projection(h, FactProjection(hb, FACT_ELEMENT_BELOW, false, hi))
    at = fact_constant(h, 0); retained = h
    got = fact_project(h, hb, at, true, T_I8); bound = fact_bound(h, got)
    if bound.lo != -10 or bound.hi != 20 or not bound.nz or not fact_distance(h, got, hi, -1): fail(30)
    if retained.projections.len() != 2 or retained.differences.len() != 0: fail(31)
    print("rows {h.differences.len()}")
    loop d in h.differences: print("{d.a} {d.b} {d.limit} {d.at}")
    # Tuple components and integer-row hulls use the same recursive builder.
    tup = mk_tuple([T_I8, T_INT]); tb = fact_new(h, FactBound(), FactTerm(type=mk_array(tup)))
    fact_add_projection(h, FactProjection(tb, fact_component_selector(0, false), false, hv))
    tv = fact_project(h, tb, at, true, tup)
    part = fact_project(h, tv, 0, false, T_I8)
    if fact_bound(h, part).lo != -10 or fact_bound(h, part).hi != 20: fail(32)
    matrix = fact_new(h, FactBound(), FactTerm(type=mk_array(row_type)))
    fact_add_projection(h, FactProjection(matrix, fact_component_selector(FACT_ROW_ELEMENTS, false), false, hv))
    row = fact_project(h, matrix, at, true, row_type)
    ri = fact_projection_find(h, row, FACT_ELEMENT_VALUE, false)
    if ri < 0 or h.projections[ri].value != hv: fail(33)
    # A row source shares the selected row's exact length, while length hulls
    # create separate identities for separate elements.
    fact_hull_owner = -1; r = FactState()
    source = fact_new(r, FactBound(), FactTerm(type=mk_array(row_type)))
    target = fact_new(r, FactBound(), FactTerm(type=mk_array(row_type)))
    idx = fact_constant(r, 2)
    sr = fact_project(r, source, idx, true, row_type)
    sl = fact_project(r, sr, -1, false, T_INT); fact_set_bound(r, sl, FactBound(3, 6))
    fact_add_projection(r, FactProjection(target, FACT_ROW_SOURCE, false, source))
    target_row = fact_project(r, target, idx, true, row_type)
    if fact_project(r, target_row, -1, false, T_INT) != sl: fail(34)
    strings = fact_new(r, FactBound(), FactTerm(type=mk_array(T_STR)))
    hull = fact_new(r, FactBound(2, 8)); fact_add_projection(r, FactProjection(strings, FACT_ELEMENT_LENGTH, false, hull))
    x = fact_project(r, strings, idx, true, T_STR); idx2 = fact_constant(r, 3)
    y = fact_project(r, strings, idx2, true, T_STR)
    xl = fact_project(r, x, -1, false, T_INT); yl = fact_project(r, y, -1, false, T_INT)
    if xl == yl or fact_bound(r, xl).lo != 2 or fact_bound(r, yl).hi != 8: fail(35)
    same = fact_new(r, FactBound(4, 7)); strings2 = fact_new(r, FactBound(), FactTerm(type=mk_array(T_STR)))
    fact_add_projection(r, FactProjection(strings2, FACT_ELEMENT_SAME_LENGTH, false, same))
    x = fact_project(r, strings2, idx, true, T_STR)
    if fact_project(r, x, -1, false, T_INT) != same: fail(36)
    # Projection cap declines publication, without modifying a retained state.
    cap = FactState(); cb = fact_new(cap, FactBound(), FactTerm(type=arr)); cv = fact_constant(cap, 1)
    loop i in [0..FACT_CAP): fact_add_projection(cap, FactProjection(cb, i, false, cv))
    old = cap; v = fact_project(cap, cb, 999, false, T_INT)
    if v == 0 or cap.projections.len() != FACT_CAP or old.ids.len() + 1 != cap.ids.len(): fail(40)
    print("projection construction ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_facts_projection_build_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)

@pytest.mark.parametrize('flags', [(), ('--release',)])
def test_facts_projection_build_program_twins(compiler, tmp_path, monkeypatch, flags):
    globs = ('refine_proven_rows/*.dewy', 'refine_length_helpers/*.dewy',
             'dict_sibling/*.dewy', 'self_length/*.dewy', 'facts/component*.dewy',
             'facts/constructor*.dewy', 'facts/inventory*.dewy', 'facts/snapshot*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in globs for p in (ROOT / 'tests/cases').glob(glob)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, flags, leaves=LEAF) >= 10
