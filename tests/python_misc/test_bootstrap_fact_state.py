"""Native relational fact joins/widening, including vacuous element facts."""

import subprocess
from pathlib import Path

from test_bootstrap_intervals import spelling

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def fact(key):
    def term(key):
        return f"facts.Term[{-key - 1} 'length']" if key < 0 else f'facts.Term[{key}]'

    def name(key):
        return f'length:{-key - 1}' if key < 0 else f'value:{key}'

    if key >= 0 or bounds._is_length_key(key):
        return f'facts.value({term(key)})', f'v:{name(key)}'
    remainder = bounds._decode_remainder_fact(key)
    if remainder is not None:
        subject, upper, offset = remainder
        return f'facts.remainder({term(subject)} {term(upper)} {offset})', f'r:{name(subject)}:{name(upper)}:{offset}'
    order = bounds._decode_order_fact(key)
    if order is not None:
        small, large = order
        return f'facts.order({term(small)} {term(large)})', f'o:{name(small)}:{name(large)}'
    index, sequence = bounds._decode_index_fact(key)
    if sequence == bounds._NONZERO_MARK:
        return f'facts.nonzero({index})', f'n:{index}'
    return f'facts.index({index} {sequence})', f'i:{index}:{sequence}'


def test_native_fact_state_matches_hosted(tmp_path):
    span = Span(0, 0)
    registry = bindings.BindingRegistry()
    registry.by_id[3] = bindings.Binding(3, 'counter', 'param', span, 'int8')
    element = 524288
    registry.by_id[element] = bindings.Binding(element, 'items.*', 'value', span, route_root=2)
    registry.route_paths[element] = ('*',)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), hir.Block(span, 'void', [], True))
    validator.max_length = 1024
    length = bounds._length_key
    order = bounds._order_key
    remainder = bounds._remainder_key
    interval = bounds.Interval
    states = [
        {},
        {1: interval(0, 0), length(2): interval(0, 0)},
        {1: interval(0, 5), length(2): interval(5, 10), order(1, length(2)): interval(0, None)},
        {1: interval(2, 7), length(2): interval(7, 12), order(1, length(2)): interval(0, None)},
        {length(2): interval(1, 5), order(element, length(4)): interval(1, None), bounds._nonzero_key(element): interval(None, None)},
        {length(2): interval(0, 0), length(4): interval(0, 10)},
        {3: interval(0, 2), remainder(1, length(2), 3): interval(4, None)},
        {3: interval(-1, 4), remainder(1, length(2), 3): interval(2, None)},
        {length(2): interval(3, 8), order(length(2), length(4)): interval(2, None),
         order(length(4), length(2)): interval(-4, None),
         remainder(length(2), length(4), 3): interval(1, None),
         remainder(length(4), length(2), 3): interval(2, None),
         order(length(2), length(2)): interval.exact(0),
         bounds._index_fact_key(1, 2): interval(None, None), bounds._nonzero_key(3): interval.exact(1)},
    ]
    changes = [interval.exact(1), interval.exact(-1), interval(0, 2), interval(None, 0), interval(-7, 0), interval(None, None)]
    lines = []
    for i, state in enumerate(states):
        lines.append(f'    let s{i}:facts.State = []')
        for key, value in state.items():
            lo = 'none' if value.lower is None else f'({value.lower})'
            hi = 'none' if value.upper is None else f'({value.upper})'
            lines.append(f'    facts.put(@s{i} {fact(key)[0]} ranges.Interval[{lo} {hi} {str(value.capped).lower()}])')
    lines.append('    let states:array<facts.State> = [' + ' '.join(f's{i}' for i in range(len(states))) + ']')
    expected = []
    for i, left in enumerate(states):
        for j, right in enumerate(states):
            for operation, result in [
                ('join', validator._join_states([left, right])),
                ('narrow', validator._narrow_states(left, right)),
                ('widen', validator._widen_states(left, right)),
            ]:
                expected.extend(f'{i}:{j}:{operation}|{fact(key)[1]}|{spelling(value)}' for key, value in result.items())
        result = validator._shifted_facts(left, 3, 1)
        expected.extend(f'{i}:shift|{fact(key)[1]}|{spelling(value)}' for key, value in result.items())
        result = dict(left)
        result.pop(3, None)
        bounds._drop_index_facts(result, index_id=3)
        expected.extend(f'{i}:forget|{fact(key)[1]}|{spelling(value)}' for key, value in result.items())
        for j, change in enumerate(changes):
            result = dict(left)
            bounds._change_length_facts(result, 2, change)
            expected.extend(f'{i}:{j}:length|{fact(key)[1]}|{spelling(value)}' for key, value in result.items())
        result = dict(left)
        result.pop(length(2), None)
        bounds._drop_index_facts(result, array_id=2)
        expected.extend(f'{i}:forget-length|{fact(key)[1]}|{spelling(value)}' for key, value in result.items())
    changes_text = ' '.join(f'ranges.Interval[{"none" if c.lower is None else f"({c.lower})"} {"none" if c.upper is None else f"({c.upper})"}]' for c in changes)
    source = tmp_path / 'fact_state.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
emit = (prefix:string state:facts.State):>void => {{
    loop entry in state.values {{
        let interval = entry.interval
        let lo = if interval.lower is? none '-' else _bigint_as_string(interval.lower)
        let hi = if interval.upper is? none '+' else _bigint_as_string(interval.upper)
        printl("{{prefix}}|{{entry.fact.key}}|{{lo}},{{hi}},{{interval.capped}}")
    }}
}}
main = ():>int64 => {{
    let context = facts.Context[cap=1024 widths=[3 -> ranges.Interval[(-128) 127]] element_roots=[{element} -> 2]]
{chr(10).join(lines)}
    let changes:array<ranges.Interval> = [{changes_text}]
    loop i in 0.. and i <? states.length {{
        let left = states[i]
        loop j in 0.. and j <? states.length {{
            let right = states[j]
            emit("{{i}}:{{j}}:join" facts.join([left right] context))
            emit("{{i}}:{{j}}:narrow" facts.narrow(left right context))
            emit("{{i}}:{{j}}:widen" facts.widen(left right context))
        }}
        emit("{{i}}:shift" facts.shifted(left facts.Term[3] 1))
        loop j in 0.. and j <? changes.length {{
            let changed = left
            facts.change_length(@changed 2 changes[j])
            emit("{{i}}:{{j}}:length" changed)
        }}
        let lost_length = left
        facts.forget(@lost_length facts.Term[2 'length'])
        emit("{{i}}:forget-length" lost_length)
        facts.forget(@left facts.Term[3])
        emit("{{i}}:forget" left)
    }}
    # Ids beyond the hosted packing width remain distinct across all kinds.
    if facts.order(facts.Term[2097152] facts.Term[1]).key =? facts.order(facts.Term[1] facts.Term[2097152]).key return 1
    if facts.index(1048576 1).key =? facts.nonzero(1048576).key return 2
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert sorted(result.stdout.splitlines()) == sorted(expected)
