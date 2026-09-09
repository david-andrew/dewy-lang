"""Native relational proof search and fact copies against the hosted pass."""

import subprocess
from pathlib import Path

from test_bootstrap_fact_state import fact
from test_bootstrap_intervals import spelling

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def term(id):
    return f"facts.Term[{-id-1} 'length']" if id < 0 else f'facts.Term[{id}]'


def test_native_relations_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()
    span = Span(0, 0)
    for id, type_ in [(1, 'int8'), (2, ty.ArrayType('int64', 5)), (3, 'int64'), (4, ty.StringType(3))]:
        registry.by_id[id] = bindings.Binding(id, f'v{id}', 'value', span, type_)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), hir.Block(span, 'void', [], False))
    validator.max_length = 1024
    length, order, interval = bounds._length_key, bounds._order_key, bounds.Interval
    states = [
        {},
        {1: interval(0, 4), length(2): interval(4, 7)},
        {order(1, 3): interval(2, None), order(3, length(2)): interval(1, None)},
        {order(1, 3): interval(0, None), order(3, 1): interval(0, None)},
        {bounds._index_fact_key(1, 2): interval(None, None), bounds._nonzero_key(1): interval.exact(1)},
        {bounds._remainder_key(1, length(2), 3): interval(3, None), 3: interval(0, 7)},
    ]
    terms = [1, 3, length(2), length(4)]
    gaps = [-1, 0, 1, 3]
    lines, expected = [], []
    for i, state in enumerate(states):
        lines.append(f'    let s{i}:facts.State = []')
        for key, value in state.items():
            lo = 'none' if value.lower is None else f'({value.lower})'
            hi = 'none' if value.upper is None else f'({value.upper})'
            lines.append(f'    facts.put(@s{i} {fact(key)[0]} ranges.Interval[{lo} {hi}])')
        for left in terms:
            for right in terms:
                for gap in gaps:
                    expected.append(f'proof|{i}|{term(left)}|{term(right)}|{gap}|{str(validator._ordered(left, right, gap, state)).lower()}')
        for label, source, target in [('scalar', 1, 5), ('length', length(2), length(6)), ('offset', 3, 7)]:
            copied = dict(state)
            validator._copy_relational_facts(copied, source, target)
            expected.extend(f'{label}{i}|{fact(key)[1]}|{spelling(value)}' for key, value in copied.items())
        expected.extend(f'subject{i}|{fact(key)[1]}|{spelling(value)}' for key, value in validator._facts_of(state, 1).items())
    lines.append('    let states:array<facts.State> = [' + ' '.join(f's{i}' for i in range(len(states))) + ']')
    source = tmp_path / 'relations.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/relations.dewy'}" as relations
term_text = (value:facts.Term):>string => if value.projection =? 'length' "facts.Term[{{value.binding_id}} 'length']" else "facts.Term[{{value.binding_id}}]"
emit = (label:string state:facts.State):>void => {{
    loop entry in state.values {{
        let value = entry.interval
        let lo = if value.lower is? none '-' else _bigint_as_string(value.lower)
        let hi = if value.upper is? none '+' else _bigint_as_string(value.upper)
        printl("{{label}}|{{entry.fact.key}}|{{lo}},{{hi}},{{value.capped}}")
    }}
}}
main = ():>int64 => {{
    let context = relations.Context[
        facts.Context[cap=1024 widths=[1 -> ranges.Interval[(-128) 127] 3 -> ranges.Interval[(-9223372036854775808) 9223372036854775807]]]
        [2 -> 5 4 -> 3]
    ]
{chr(10).join(lines)}
    let terms:array<facts.Term> = [{' '.join(term(t) for t in terms)}]
    let gaps:array<bigint> = [(-1) 0 1 3]
    loop i in 0.. and i <? states.length {{
        let state = states[i]
        loop left in terms {{ loop right in terms {{ loop gap in gaps {{
            printl("proof|{{i}}|{{term_text(left)}}|{{term_text(right)}}|{{_bigint_as_string(gap)}}|{{relations.ordered(left right gap state context)}}")
        }} }} }}
        let scalar = state
        relations.copy_relational(@scalar facts.Term[1] facts.Term[5])
        emit("scalar{{i}}" scalar)
        let length = state
        relations.copy_relational(@length facts.Term[2 'length'] facts.Term[6 'length'])
        emit("length{{i}}" length)
        let offset = state
        relations.copy_relational(@offset facts.Term[3] facts.Term[7])
        emit("offset{{i}}" offset)
        emit("subject{{i}}" relations.facts_of(state facts.Term[1]))
    }}
    let lengths:facts.State = []
    facts.put(@lengths facts.index(1 2) ranges.UNKNOWN)
    relations.copy_relational(@lengths facts.Term[2 'length'] facts.Term[5])
    $runtime_assert relations.ordered(facts.Term[1] facts.Term[5] 1 lengths context)
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert sorted(result.stdout.splitlines()) == sorted(expected)
