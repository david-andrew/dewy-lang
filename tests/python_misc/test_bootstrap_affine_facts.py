"""Native bounds evidence for affine assignments, sums, and differences."""

import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_fact_state import fact
from test_bootstrap_initialization import type_builder
from test_bootstrap_intervals import spelling

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)


def test_native_affine_facts_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()

    def reference(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    def number(value):
        return hir.Integer(LOC, ty.IntegerLiteralType(value), '0d', value)

    def binary(name, left, right):
        fn = hir.ExpressedIdentifier(LOC, ty.FunctionType([], [], None, 'int64'), name)
        return hir.FunctionCall(LOC, 'int64', fn, [left, right], {})

    i, j = reference('i', 'int64'), reference('j', 'int64')
    text, prefix = reference('text', ty.StringType(None)), reference('prefix', ty.StringType(None))
    length = hir.StringLength(LOC, 'int64', text)
    prefix_length = hir.StringLength(LOC, 'int64', prefix)
    sums = [binary('__add__', i, j), binary('__add__', j, i),
            binary('__add__', j, number(3)), binary('__add__', number(1), j),
            binary('__sub__', prefix_length, number(1)), binary('__add__', prefix_length, number(1)),
            binary('__sub__', length, prefix_length), binary('__sub__', length, i),
            binary('__sub__', i, i), binary('__mul__', i, number(2))]
    assignments = [hir.Assign(LOC, 'void', i, op, value) for op, value in [
        ('+=', number(2)), ('-=', number(-1)), ('+=', j), ('*=', number(2)),
        ('=', binary('__add__', i, number(2))), ('=', binary('__sub__', i, number(2))),
        ('=', binary('__add__', number(2), i)),
        ('=', hir.Obligation(LOC, 'int64', binary('__add__', i, number(2)),
                            ty.RefinedType('int64', (ty.Proposition('self', '>=?', 0),)), 'store contract')),
    ]]
    root = hir.Block(LOC, 'void', [*sums, *assignments], False)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root)
    validator.max_length = 1024
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    registry_lines = [f'    registry.by_id[{b.id}] = bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]'
                      for b in registry.by_id.values()]
    interval, order, length_key = bounds.Interval, bounds._order_key, bounds._length_key
    states = [{}, {
        i.binding_id: interval(0, 4), j.binding_id: interval(1, 7),
        order(i.binding_id, length_key(text.binding_id)): interval(5, None),
        bounds._remainder_key(j.binding_id, length_key(text.binding_id), i.binding_id): interval(2, None),
        length_key(prefix.binding_id): interval(3, 9),
        order(length_key(prefix.binding_id), length_key(text.binding_id)): interval(0, None),
    }]
    checks, expected = [], []
    for index, assignment in enumerate(assignments):
        expected.append(f'shift{index}|{validator._assignment_shift(assignment)}')
        checks.append(f'''    let assign{index} = hir.node_at(nodes {names[id(assignment)]})
    $runtime_assert assign{index} is? hir.Assign
    printl("shift{index}|{{endpoint(terms.assignment_shift(assign{index} env @registry))}}")''')
    for state_index, state in enumerate(states):
        checks.append('    state.clear')
        for key, value in state.items():
            lo = 'none' if value.lower is None else f'({value.lower})'
            hi = 'none' if value.upper is None else f'({value.upper})'
            checks.append(f'    flow.put(@state {fact(key)[0].replace("facts.", "flow.")} ranges.Interval[{lo} {hi}])')
        for index, node in enumerate(sums):
            seeded = dict(state)
            validator._seed_sum_facts(100, node, seeded)
            expected.extend(f'sum{state_index}_{index}|{fact(key)[1]}|{spelling(value)}' for key, value in seeded.items())
            difference = validator._difference_bound(node, state)
            expected.append(f'difference{state_index}_{index}|none' if difference is None else f'difference{state_index}_{index}|{spelling(difference)}')
            checks.append(f'''    let s{state_index}_{index} = state
    terms.seed_sum(@s{state_index}_{index} 100 {names[id(node)]} env context @registry)
    emit("sum{state_index}_{index}" s{state_index}_{index})
    emit_interval("difference{state_index}_{index}" terms.difference_bound({names[id(node.pos_args[0])]} {names[id(node.pos_args[1])]} state env @registry))''')
    source = tmp_path / 'affine_facts.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/value_bounds.dewy'}" as values
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/term_facts.dewy'}" as terms
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as flow
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/relations.dewy'}" as relations
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
endpoint = (value:bigint?):>string => if value is? none 'None' else _bigint_as_string(value)
emit_interval = (label:string interval:ranges.Interval?):>void => {{
    if interval is? none {{ printl("{{label}}|none") }}
    else {{
        let lo = if interval.lower is? none '-' else _bigint_as_string(interval.lower)
        let hi = if interval.upper is? none '+' else _bigint_as_string(interval.upper)
        printl("{{label}}|{{lo}},{{hi}},{{interval.capped}}")
    }}
}}
emit = (label:string state:flow.State):>void => {{
    loop entry in state.values {{ emit_interval("{{label}}|{{entry.fact.key}}" entry.interval) }}
}}
main = ():>int64 => {{
    let span = Span[0 0]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let registry = bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env = values.Environment[nodes type_nodes registry 1024]
    let context = relations.Context[flow.Context[cap=1024 widths=[
        {i.binding_id} -> ranges.Interval[(-9223372036854775808) 9223372036854775807]
        {j.binding_id} -> ranges.Interval[(-9223372036854775808) 9223372036854775807]
    ]]]
    let state:flow.State = []
{chr(10).join(checks)}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert sorted(result.stdout.splitlines()) == sorted(expected)
