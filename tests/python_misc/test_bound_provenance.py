"""Numerically valid transfers must retain their address-cap dependency."""

from pathlib import Path

from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir
from dewy.semantic.analyze import bounds as b


def validator():
    loc = Span(0, 0)
    return b._BoundsValidator(bindings.BindingRegistry(), SrcFile(None, ''), hir.Block(loc, 'void', [], True))


def test_nonzero_narrowing_preserves_cap_dependency():
    check = validator()
    value = hir.ExpressedIdentifier(Span(0, 0), 'int64', 'value', binding_id=1)
    interval = b.Interval(0, 10, capped=True)
    state = {1: interval, b._nonzero_key(1): b.Interval.exact(1)}
    for result in [check._tightened(value, interval, state), check._eval_expressed_identifier(value, state, validate=False)]:
        assert result.lower == 1 and result.upper == 10 and result.capped


def test_length_and_remainder_transfers_keep_both_dependencies():
    check = validator()
    key = b._remainder_key(1, b._length_key(2), 3)
    state = {key: b.Interval(4, None, capped=True)}
    shifted = check._shifted_facts(state, 3, 1)
    assert shifted[key].lower == 3 and shifted[key].capped
    b._change_length_facts(state, 2, b.Interval.exact(1))
    assert state[key].lower == 5 and state[key].capped
    state[key] = b.Interval(4, None)
    b._change_length_facts(state, 2, b.Interval(1, 2, capped=True))
    assert state[key].lower == 5 and state[key].capped


def test_implied_relations_and_length_widening_record_the_cap():
    check = validator()
    length = b._length_key(2)
    state = {1: b.Interval(0, 0, capped=True), length: b.Interval(2, 5)}
    implied = check._implied(state, b._order_key(1, length))
    assert implied.lower == 2 and implied.capped
    widened = check._widen_states({length: b.Interval(0, 1)}, {length: b.Interval(0, 2)})
    assert widened[length].upper == check.max_length and widened[length].capped
    unchanged = check._widen_states({length: b.Interval(0, 1)}, {length: b.Interval(0, 1)})
    assert not unchanged[length].capped


ROOT = Path(__file__).resolve().parents[2]
CASES = ['''
import p"FACTS" as facts
import p"RANGES" as ranges
main=():>int64=>{
    let state=facts.State[]
    let key=facts.remainder(facts.Term[1] facts.Term[2 'length'] 3)
    facts.put(@state key ranges.Interval[4 none true])
    facts.change_length(@state 2 ranges.Interval[1 1])
    let changed=facts.lookup(state key)
    if changed is? none or changed.lower is? none or changed.lower not=? 5 or not changed.capped return 1
    let shifted=facts.shifted(state facts.Term[3] 1)
    let moved=facts.lookup(shifted key)
    if moved is? none or moved.lower is? none or moved.lower not=? 4 or not moved.capped return 2
    let previous=facts.State[]
    let current=facts.State[]
    let length=facts.value(facts.Term[2 'length'])
    facts.put(@previous length ranges.Interval[0 1])
    facts.put(@current length ranges.Interval[0 2])
    let context=facts.Context[1024]
    let widened=facts.widen(previous current context)
    let measured=facts.lookup(widened length)
    if measured is? none or measured.upper is? none or measured.upper not=? 1024 or not measured.capped return 3
    let exact=facts.State[]
    facts.put(@exact facts.value(facts.Term[1]) ranges.Interval[0 0 true])
    facts.put(@exact length ranges.Interval[2 5])
    let implied=facts.implied(exact facts.order(facts.Term[1] facts.Term[2 'length']) context)
    if implied isnt? ranges.Interval or implied.lower is? none or implied.lower not=? 2 or not implied.capped return 4
    return 42
}
'''.replace('FACTS', str(ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'))
   .replace('RANGES', str(ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'))]


def test_native_bound_provenance(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
