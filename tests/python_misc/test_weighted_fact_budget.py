"""Aliases of a many-term invariant must not enumerate exponential rows."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir
from dewy.semantic.analyze import bounds
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_derived_weighted_rows_have_a_finite_budget():
    validator = bounds._BoundsValidator(bindings.BindingRegistry(), SrcFile(None, ''),
                                      hir.Block(Span(0, 0), 'void', [], True))
    weights = [(index, 1) for index in range(1, 17)]
    state = {bounds._linear_key(weights): bounds.Interval(0, None)}
    for index in range(1, 17):
        validator._copy_relational_facts(state, index, index + 64)
        assert len(state) <= 128
    first = bounds._linear_key([(65, 1), *weights[1:]])
    last = bounds._linear_key([(index + 64, weight) for index, weight in weights])
    assert first in state
    assert last not in state  # exhausting inference supplies no evidence


def test_native_derived_weighted_budget_and_reclamation(tmp_path):
    source = tmp_path / 'weighted-budget.dewy'
    source.write_text(f'''import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/relations.dewy'}" as relations
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
main=():>int64=>{{
    let weights:array<facts.Coefficient>=[]
    loop index in 1..16 {{weights.push(facts.Coefficient[facts.Term[index] 1])}}
    let state=facts.State[]
    let original=facts.linear(weights)
    facts.put(@state original ranges.Interval[0 none])
    loop index in 1..16 {{
        relations.copy_relational(@state facts.Term[index] facts.Term[index+64])
        if state.values.length>?128 or state.linear_count>?128 return 1
    }}
    let first:array<facts.Coefficient>=[] let last:array<facts.Coefficient>=[]
    loop index in 1..16 {{
        first.push(facts.Coefficient[facts.Term[if index=?1 65 else index] 1])
        last.push(facts.Coefficient[facts.Term[index+64] 1])
    }}
    if not facts.contains(state facts.linear(first)) return 2
    if facts.contains(state facts.linear(last)) return 3
    loop state.values.length>?0 {{facts.remove(@state state.values[state.values.length-1].fact)}}
    if state.linear_count not=?0 return 4
    facts.put(@state original ranges.Interval[0 none])
    return if state.linear_count=?1 and facts.contains(state original) 42 else 5
}}
''')
    execute(tmp_path, 'weighted-budget', codegen(SrcFile.from_path(source), debug_locations=False))
