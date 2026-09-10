"""Native expression/length proofs, with evaluation supplied separately.

The interval snapshot is computed by the hosted evaluator here; this tests
the proof search, not a claim that the native HIR evaluator is complete.
"""

import dataclasses
import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_fact_state import fact
from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)


def test_native_length_proofs_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()

    def reference(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    def number(value):
        return hir.Integer(LOC, ty.IntegerLiteralType(value), '0d', value)

    def binary(name, left, right):
        function = hir.ExpressedIdentifier(LOC, ty.FunctionType([], [], None, 'int64'), name)
        return hir.FunctionCall(LOC, 'int64', function, [left, right], {})

    text = reference('text', ty.StringType(None))
    other = reference('other', ty.StringType(None))
    fixed = reference('fixed', ty.ArrayType('int64', 5))
    i, j = reference('i', 'int64'), reference('j', 'int64')
    length = hir.StringLength(LOC, 'int64', text)
    other_length = hir.StringLength(LOC, 'int64', other)
    end = binary('__sub__', length, number(1))
    queries = [i, j, length, other_length, number(0), number(4), number(-1), end,
               binary('__sub__', length, number(0)), binary('__sub__', end, number(2)),
               hir.Transmute(LOC, 'uint64', i), hir.Transmute(LOC, 'uint64', end)]
    for op in ['__add__', '__sub__', '__mul__']:
        queries.extend(binary(op, left, right) for left, right in [
            (i, number(1)), (number(2), i), (i, number(-1)), (i, j), (j, i),
        ])
    queries.extend([binary('__add__', length, number(2)), binary('__sub__', length, number(-2))])
    for op in ['<?', '<=?', '>?', '>=?', '=?']:
        result = ty.RefinedType('int64', (ty.Proposition('self', op, 0, term='src'),))
        signature = ty.FunctionType([ty.PosOrKwArg('src', text.type, True)], [], None, result)
        function = hir.ExpressedIdentifier(LOC, signature, 'measure')
        for argument in [text, other, hir.StringSlice(LOC, text.type, text, hir.Range(LOC, 'range', '[)', None, i, None))]:
            queries.append(hir.FunctionCall(LOC, result, function, [argument], {}))
    queries.append(hir.Obligation(LOC, 'int64', end, ty.RefinedType('int64', (ty.Proposition('self', '>=?', 0),)), 'index'))
    root = hir.Block(LOC, 'void', [*queries, fixed], False)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root)
    validator.max_length = 1024
    interval, order, length_key = bounds.Interval, bounds._order_key, bounds._length_key
    text_key, other_key = length_key(text.binding_id), length_key(other.binding_id)
    states = [
        {},
        {text_key: interval(5, 8), i.binding_id: interval(0, 4), j.binding_id: interval(8, 12)},
        {bounds._index_fact_key(i.binding_id, text.binding_id): interval(None, None)},
        {order(i.binding_id, j.binding_id): interval(1, None), order(j.binding_id, text_key): interval(2, None)},
        {bounds._remainder_key(i.binding_id, other_key, j.binding_id): interval(2, None), order(other_key, text_key): interval(1, None)},
        {order(text_key, i.binding_id): interval(2, None), i.binding_id: interval(0, None)},
        {order(other_key, text_key): interval(0, None), i.binding_id: interval(-1, 7)},
        {order(other_key, text_key): interval(0, None), i.binding_id: interval(0, 7)},
    ]
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    registry_lines = [f'    registry.by_id[{b.id}] = bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]'
                      for b in registry.by_id.values()]
    # Retain identity sharing, just as the HIR arena serializer does.
    nodes = {}

    def visit(value):
        if isinstance(value, hir.AST):
            if id(value) in nodes:
                return
            nodes[id(value)] = value
            for field in dataclasses.fields(value):
                visit(getattr(value, field.name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)

    visit(root)

    def native_interval(value):
        lo = 'none' if value.lower is None else f'({value.lower})'
        hi = 'none' if value.upper is None else f'({value.upper})'
        return f'ranges.Interval[{lo} {hi} {str(value.capped).lower()}]'

    checks, expected = [], []
    sequences = [text.binding_id, other.binding_id, fixed.binding_id]
    gaps = [-1, 0, 1, 2, 4]
    for state_index, state in enumerate(states):
        snapshot = []
        for node_id, node in nodes.items():
            value = validator._eval(node, dict(state), validate=False)
            if value is not None:
                snapshot.append(f'{names[node_id]} -> {native_interval(value)}')
        entries = [f'    flow.put(@state {fact(key)[0].replace("facts.", "flow.")} {native_interval(value)})'
                   for key, value in state.items()]
        checks.append(f'''    state.clear
{chr(10).join(entries)}
    let context{state_index} = proofs.Context[env relation_context]
    let observed{state_index}:dict<addr ranges.Interval>=[{' '.join(snapshot)}]
    emit_queries({state_index} queries sequences gaps state context{state_index} observed{state_index} @registry)''')
        for query_index, query in enumerate(queries):
            for sequence in sequences:
                for gap in gaps:
                    upper = validator._bounded_by_length(query, sequence, gap, dict(state))
                    lower = validator._lower_bounded_by_length(query, sequence, gap, dict(state))
                    expected.append(f'{state_index}|{query_index}|{sequence}|{gap}|{str(upper).lower()}|{str(lower).lower()}')
    # Exercise both proof directions, and ensure failures are represented too.
    assert any(row.endswith('|true|false') for row in expected)
    assert any(row.endswith('|false|true') for row in expected)
    assert any(row.endswith('|true|true') for row in expected)
    assert any(row.endswith('|false|false') for row in expected)
    source = tmp_path / 'length_proofs.dewy'
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('facts', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('proofs', 'analyze/length_proofs.dewy'),
        ('flow', 'analyze/fact_state.dewy'), ('ranges', 'analyze/intervals.dewy'), ('relations', 'analyze/relations.dewy'),
    ])
    source.write_text(f'''from reporting import Span
{imports}
emit_queries = (label:addr queries:array<addr> sequences:array<addr> gaps:array<bigint> state:flow.State context:proofs.Context observed:dict<addr ranges.Interval> @registry:bindings.Registry):>void => {{
    loop index in 0.. and index <? queries.length {{
        loop sequence in sequences {{
            loop gap in gaps {{
                let upper = proofs.upper(queries[index] sequence gap state context observed @registry)
                let lower = proofs.lower(queries[index] sequence gap state context observed @registry)
                printl("{{label}}|{{index}}|{{sequence}}|{{_bigint_as_string(gap)}}|{{upper}}|{{lower}}")
            }}
        }}
    }}
}}
main = ():>int64 => {{
    let span = Span[0 0]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let registry = bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env = values.Environment[nodes type_nodes registry 1024]
    let relation_context = relations.Context[flow.Context[cap=1024 widths=[
        {i.binding_id} -> ranges.Interval[(-9223372036854775808) 9223372036854775807]
        {j.binding_id} -> ranges.Interval[(-9223372036854775808) 9223372036854775807]
    ]] minimum_lengths=[{fixed.binding_id} -> 5]]
    let queries:array<addr> = [{' '.join(names[id(query)] for query in queries)}]
    let sequences:array<addr> = [{' '.join(map(str, sequences))}]
    let gaps:array<bigint> = [(-1) 0 1 2 4]
    let state:flow.State = []
{chr(10).join(checks)}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
