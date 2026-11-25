"""Refinement checks and entry transfers keep holders, validation, probes and snapshots."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAVES = ('refine_transfers',)
DRIVER = '''use 'main.jo'
use 'refine.jo'
use 'refinement_types.dewy'
use 'facts.jo'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
use 'facts_compare.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'checker_types.dewy'
use 'checker_state.dewy'
use 'check.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'string_domains.jo'
use 'witness.jo'
use 'util.jo'
use 'expr.jo'
new_type = (info: TypeInfo) -> int:
    id = types.len(); types.push(info); id
check_node = (t: int) -> int:
    n = nodes.len(); nodes.push(Node(kind=.conv, aux=i32(int(CV.refinement)), aux2=i32(t))); n
main = ():
    init_types()
    fact_terms = [FactTerm()]
    fact_query = false; fact_owner = 0; fact_hull_owner = -1
    fact_validated = {}; fact_probe = {}; fact_probe_on = false
    fact_policy = FactPolicy.RuntimeAllowed
    nodes = fill(Node(), 4)
    ref_predicates = [[], [RefAtom(.le, RefTerm(1, -3), RefTerm()), RefAtom(.le, RefTerm(), RefTerm(1, 5))]]
    scalar = new_type(TypeInfo(kind=.refined, elem=i32(T_INT), st=1))
    inferred = new_type(TypeInfo(kind=.var, ref=i32(scalar)))
    s = FactState()
    # Proven: metadata kept, validated, nothing assumed.
    inside = fact_new(s, FactBound(0, 4), FactTerm(type=T_INT))
    n = check_node(inferred)
    ref_fact_holder = 77
    ref_check(n, inside, [], s)
    assert(ref_fact_holder == 77 and nodes[n].aux2 == i32(scalar) and nodes[n].ival == 1)
    assert(fact_validated.has(n) and fact_bound(s, inside).lo == 0)
    # Unknown under runtime checks: erased metadata 0, the contract is assumed afterwards.
    wide = fact_new(s, FactBound(-10, 10), FactTerm(type=T_INT))
    saved = s
    n = check_node(scalar)
    fact_probe_on = true
    ref_check_held(n, wide, [], s)
    b = fact_bound(s, wide); before = fact_bound(saved, wide)
    assert(nodes[n].ival == 0 and fact_validated[n] and not fact_probe[n])
    assert(b.lo == -3 and b.hi == 5 and before.lo == -10 and before.hi == 10)
    fact_probe_on = false
    # Speculation assumes without validating; a dead state only rewrites the type.
    fact_speculating = 1
    other = fact_new(s, FactBound(-10, 10), FactTerm(type=T_INT))
    n = check_node(inferred)
    ref_check_held(n, other, [], s)
    assert(fact_bound(s, other).hi == 5 and nodes[n].aux2 == i32(inferred) and not fact_validated.has(n))
    fact_speculating = 0
    dead = FactState(live=false)
    n = check_node(inferred)
    ref_check_held(n, other, [], dead)
    assert(nodes[n].aux2 == i32(scalar) and not fact_validated.has(n))
    # Established and domain-proven checks hold without a comparison.
    n = check_node(scalar)
    ref_self_active = true; ref_self_established[n] = true
    third = fact_new(s, FactBound(-10, 10), FactTerm(type=T_INT))
    ref_check(n, third, [], s)
    assert(nodes[n].ival == 1 and fact_validated[n] and fact_bound(s, third).lo == -3)
    ref_self_active = false
    n = check_node(scalar)
    int_domain_proven[n] = true
    fourth = fact_new(s, FactBound(-10, 10), FactTerm(type=T_INT))
    ref_check_held(n, fourth, [], s)
    assert(nodes[n].ival == 1 and fact_bound(s, fourth).hi == 5)
    # A tied pair's hint is a note whenever the check may fail.
    n = check_node(scalar)
    ref_pair_hints[n] = "hint"
    notes = err_notes.len()
    fifth = fact_new(s, FactBound(-1, 1), FactTerm(type=T_INT))
    ref_check_held(n, fifth, [], s)
    assert(err_notes.len() == notes and nodes[n].ival == 1)
    hinted = n
    # Entries: no owner keeps the published entry; a mutable parameter is read afresh.
    refine_entry = [inside, wide]
    kept = ref_fact_current_entry(s)
    assert(kept.len() == 2 and kept[0] == inside and kept[1] == wide and refine_entry[1] == wide)
    locals = [Local(), Local(type=i32(T_INT)), Local(type=i32(T_INT), flags=i32(LF_MUTPARAM))]
    fns.push(FnInst(params=[1, 2], ptypes=[scalar, T_INT]))
    f = fns.len() - 1
    refine_fact_entry(f, s)
    assert(refine_entry.len() == 2 and refine_entry[0] != 0 and refine_entry[1] != 0)
    b = fact_bound(s, refine_entry[0])
    assert(b.lo == -3 and b.hi == 5)
    entry = refine_entry
    fact_owner = f
    current = ref_fact_current_entry(s)
    assert(current[0] == entry[0] and refine_entry[1] == entry[1])
    fact_owner = 0
    print("refinement checks keep holders, validation, probes and entries {current.len()}")
    # A refuted check reports its tied pair's hint and stops the build.
    sixth = fact_new(s, FactBound(10, 20), FactTerm(type=T_INT))
    ref_check_held(hinted, sixth, [], s)
    print("not reached")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_checks_state_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAVES)
    modules.with_stderr = True
    compare_leaf(compiler, tmp_path, release, DRIVER, status=1, extra_stems=LEAVES, jo_doubles=modules)


def test_refine_checks_program_twins(compiler, tmp_path, monkeypatch):
    patterns = ('refinements/*.dewy', 'refine_proven_rows/*.dewy',
                'self_length/*.dewy', 'sibling_length/*.dewy', 'dict_sibling/*.dewy',
                'record_paired_fields/*.dewy', 'uint64_ceiling/*.dewy',
                'refine_length_helpers/*.dewy', 'nd_contracts/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for pattern in patterns for p in (ROOT / 'tests/cases').glob(pattern)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAVES) > 50
