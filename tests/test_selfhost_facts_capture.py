"""Recursive capture preserves branch snapshots, budgets and checked-index evidence."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAVES = ('facts_capture',)
DRIVER = '''use 'main.jo'
use 'facts.jo'
use 'facts_capture.dewy'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
use 'refinement_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'exact.jo'
use 'util.jo'
use 'source_types.dewy'
plain_ids = (values: int[]) -> int: values[0]
main = ():
    init_types()
    files = [SrcFile(path="/capture.jo", is_dewy=false)]
    fns = [FnInst()]
    nodes = fill(Node(), 20)
    fact_terms = [FactTerm()]
    exact_marks = []
    fact_query = false; fact_speculating = 0; fact_owner = 0
    s = FactState(); snapshot = s
    if fact_capture(0, s) != 0 or fact_capture_value(0, s) != 0: exit(10)
    nodes[1] = Node(kind=.int_lit, type=i32(T_INT), ival=7, pos=mkpos(0, 1))
    v = fact_capture(1, s)
    if plain_ids([v]) != v: exit(11)
    b = fact_bound(s, v)
    if b.lo != 7 or b.hi != 7 or fact_terms[v].origin != 1: exit(12)
    if snapshot.ids.len() != 0 or snapshot.bounds.len() != 0: exit(13)
    nodes[2] = Node(kind=.int_lit, type=i32(T_INT), ival=11)
    before = fact_terms.len()
    fact_speculating = 1; fact_constructor_budget = 0
    fact_loop_steps = 3; fact_loop_exhausted = false
    if fact_capture_value(2, s) != 0 or not fact_loop_exhausted or fact_loop_steps != 3 or fact_terms.len() != before: exit(14)
    fact_constructor_budget = 2; fact_loop_exhausted = false
    fact_step_limit = 3
    if fact_capture_value(2, s) != 0 or not fact_loop_exhausted or fact_loop_steps != 4 or fact_constructor_budget != 1: exit(15)
    fact_step_limit = FACT_STEPS; fact_constructor_budget = -1; fact_speculating = 0
    fact_loop_exhausted = false
    dead = FactState(live=false)
    if fact_capture_value(2, dead) != 0 or fact_terms.len() != before: exit(16)
    # Checked accesses publish success facts only in a live runtime path.
    state = FactState()
    index = fact_new(state, FactBound(-5, 12))
    length = fact_constant(state, 10)
    held = state
    fact_index_success(1, state, index, length)
    bound = fact_bound(state, index)
    if bound.lo != 0 or bound.hi != 9: exit(17)
    prior = fact_bound(held, index)
    if prior.lo != -5 or prior.hi != 12: exit(18)
    loop mode in [0..3):
        state = held
        fact_speculating = if mode == 0: 1 else: 0
        fact_query = mode == 1
        if mode == 2: state.live = false
        fact_index_success(1, state, index, length)
        bound = fact_bound(state, index)
        if bound.lo != -5 or bound.hi != 12: exit(19)
    fact_speculating = 0; fact_query = false
    print("capture snapshots and budgets ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_facts_capture_state_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAVES)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAVES, jo_doubles=modules)


def test_facts_capture_program_twins(compiler, tmp_path, monkeypatch):
    patterns = ('facts/*.dewy', 'block_scope/*.dewy', 'loan/*.dewy',
                'broadcast_facts/*.dewy', 'refine_proven_rows/*.dewy',
                'uint64_ceiling/*.dewy', 'optional/*.dewy', 'match/*.dewy',
                'exact_int/wide_unsigned_divisor*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for pattern in patterns for p in (ROOT / 'tests/cases').glob(pattern)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAVES) > 30
