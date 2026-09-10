"""Native interval transfers consume evaluated child values and current facts."""

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


def test_native_expression_interval_transfers(tmp_path):
    registry = bindings.BindingRegistry()

    def reference(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    def number(n):
        return hir.Integer(LOC, ty.IntegerLiteralType(n), '0d', n)

    def binary(name, left, right, type_='int64'):
        function = hir.ExpressedIdentifier(LOC, ty.FunctionType([], [], None, type_), name)
        return hir.FunctionCall(LOC, type_, function, [left, right], {})

    i = reference('i', 'int64')
    j = reference('j', ty.nat_type('nat64'))
    text = reference('text', ty.StringType(None))
    array = reference('array', ty.ArrayType('int64', None))
    length = hir.StringLength(LOC, 'int64', text)
    array_length = hir.ArrayLength(LOC, 'int64', array)
    end = binary('__sub__', length, number(1))
    queries = [i, j, length, array_length, hir.ValueCast(LOC, 'uint8', i)]
    for op in ['__add__', '__sub__', '__mul__', '__floordiv__', '__mod__']:
        queries.extend(binary(op, left, right) for left, right in [
            (i, j), (i, number(2)), (length, i), (number(-9), number(2)),
        ])
    slices = [hir.StringSlice(LOC, text.type, text, hir.Range(LOC, 'range', delimiters, None, left, right))
              for delimiters, left, right in [('[)', i, None), ('[]', i, end), ('[)', i, j),
                                              ('(]', number(1), number(4)), ('[]', None, None)]]
    queries.extend(hir.StringLength(LOC, 'int64', value) for value in slices)
    literal = hir.String(LOC, ty.StringLiteralType('hello'), 'hello')
    widened = hir.ValueCast(LOC, 'string', literal)
    queries.append(hir.StringLength(LOC, 'int64', widened))
    promised = ty.RefinedType('int64', (ty.Proposition('self', '>=?', 3),))
    function = hir.ExpressedIdentifier(LOC, ty.FunctionType([], [], None, promised), 'user_function')
    queries.append(hir.FunctionCall(LOC, 'int64', function, [], {}))
    # Stored results survive a later write to the binding they were read from.
    saved_sum = binary('__add__', i, number(1))
    saved_difference = binary('__sub__', i, j)
    root = hir.Block(LOC, 'void', [*queries, saved_sum, saved_difference], False)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root)
    validator.max_length = 1024
    interval = bounds.Interval
    states = [
        {},
        {i.binding_id: interval(0, 4), j.binding_id: interval(5, 9),
         bounds._length_key(text.binding_id): interval(8, 20)},
        {i.binding_id: interval(0, 4), bounds._nonzero_key(i.binding_id): interval.exact(1),
         bounds._order_key(i.binding_id, bounds._length_key(text.binding_id)): interval(1, None)},
        {i.binding_id: interval(-3, 2), j.binding_id: interval(0, 2),
         bounds._length_key(array.binding_id): interval(3, 10)},
    ]
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    registry_lines = [f'    registry.by_id[{b.id}]=bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]'
                      for b in registry.by_id.values()]
    ordered, seen = [], set()

    def visit(value):
        if isinstance(value, hir.AST):
            if id(value) in seen:
                return
            seen.add(id(value))
            for field in dataclasses.fields(value):
                visit(getattr(value, field.name))
            ordered.append(value)
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
    for index, state in enumerate(states):
        checks.append('    state.clear\n    snapshot=transfer.Snapshot[]')
        checks.extend(f'    flow.put(@state {fact(key)[0].replace("facts.", "flow.")} {native_interval(value)})'
                      for key, value in state.items())
        checks.extend(f'    transfer.record(@snapshot {names[id(node)]} state env @registry)' for node in ordered)
        for query_index, query in enumerate(queries):
            value = validator._eval(query, dict(state), validate=False)
            label = f'{index}:{query_index}'
            checks.append(f'    emit("{label}" snapshot.numbers.get({names[id(query)]}))')
            expected.append(f'{label}|none' if value is None else f'{label}|{value.lower},{value.upper}')
    checks.extend([
        f'    snapshot.numbers[{names[id(i)]}]=ranges.exact(7)',
        f'    flow.set_value(@state flow.Term[{i.binding_id}] ranges.exact(99))',
        f'    emit("saved" transfer.transfer({names[id(saved_sum)]} state snapshot env @registry))',
        f'    snapshot.numbers[{names[id(j)]}]=ranges.exact(2)',
        f'    transfer.forget(@snapshot {i.binding_id})',
        f'    flow.put(@state flow.order(flow.Term[{j.binding_id}] flow.Term[{i.binding_id}]) ranges.Interval[90 none])',
        f'    emit("historical" transfer.transfer({names[id(saved_difference)]} state snapshot env @registry))',
    ])
    expected.append('saved|8,8')
    expected.append('historical|5,5')
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('facts', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('transfer', 'analyze/expression_intervals.dewy'),
        ('flow', 'analyze/fact_state.dewy'), ('ranges', 'analyze/intervals.dewy'),
    ])
    source = tmp_path / 'expression_intervals.dewy'
    source.write_text(f'''from reporting import Span
{imports}
endpoint=(value:bigint?):>string=>if value is? none 'None' else _bigint_as_string(value)
emit=(label:string value:ranges.Interval?):>void=>{{
    if value is? none printl("{{label}}|none")
    else printl("{{label}}|{{endpoint(value.lower)}},{{endpoint(value.upper)}}")
}}
main=():>int64=>{{
    let span=Span[0 0]
    let nodes:array<hir.AST>=[]
    let type_nodes:array<types.Type>=[]
    let registry=bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env=values.Environment[nodes type_nodes registry 1024]
    let state:flow.State=[]
    let snapshot=transfer.Snapshot[]
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
