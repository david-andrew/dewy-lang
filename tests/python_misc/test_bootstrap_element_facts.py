"""Native element evidence survives copies and weakens on mixed stores."""

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


def test_native_element_facts_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()

    def reference(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    text = reference('text', ty.StringType(None))
    start = reference('start', 'int64')
    length = reference('length', 'int64')
    record_type = ty.ObjectType((ty.ObjectField('length', 'int64'), ty.ObjectField('start', 'int64')))
    array = reference('array', ty.ArrayType(record_type, None))
    result = reference('result', record_type)
    copied = reference('copied', array.type)
    scalars = reference('scalars', ty.ArrayType('int64', None))
    scalar_result = reference('scalar_result', 'int64')
    refined = reference('refined', ty.ArrayType(ty.RefinedType('int64', (ty.Proposition('self', '>?', 0),)), None))
    number = hir.Integer(LOC, ty.IntegerLiteralType(0), '0d', 0)
    value = hir.ObjectLiteral(LOC, record_type, [hir.ObjectField(LOC, 'length', length), hir.ObjectField(LOC, 'start', start)])
    unknown = hir.ObjectLiteral(LOC, record_type, [hir.ObjectField(LOC, 'length', number), hir.ObjectField(LOC, 'start', number)])
    read = hir.Index(LOC, record_type, array, number, 0)
    member = hir.MemberAccess(LOC, 'int64', read, 'length')
    root = hir.Block(LOC, ty.VOID_TYPE, [text, start, length, array, result, copied, scalars, scalar_result, refined, value, unknown, read, member], False)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root)
    base_bindings = list(registry.by_id.values())
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    word = build('int64')
    registry_lines = [f'    registry.by_id[{b.id}] = bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]'
                      for b in base_bindings]
    state, checks, expected = {}, [], []

    def put(key, interval):
        state[key] = interval
        lo = 'none' if interval.lower is None else f'({interval.lower})'
        hi = 'none' if interval.upper is None else f'({interval.upper})'
        checks.append(f'    flow.put(@state {fact(key)[0].replace("facts.", "flow.")} ranges.Interval[{lo} {hi}])')

    def snapshot(label):
        checks.append(f'    emit("{label}" state)')
        expected.extend(f'{label}|{fact(key)[1]}|{spelling(value)}' for key, value in state.items())

    def store(sequence, item, label):
        validator._store_element(state, sequence.binding_id, item, LOC)
        checks.append(f'    elements.store(@state {sequence.binding_id} {names[id(item)]} {word} span env @registry)')
        snapshot(label)

    remainder = bounds._remainder_key(length.binding_id, bounds._length_key(text.binding_id), start.binding_id)
    put(remainder, bounds.Interval(1, None))
    put(bounds._index_fact_key(start.binding_id, text.binding_id), bounds.Interval(None, None))
    put(bounds._nonzero_key(start.binding_id), bounds.Interval.exact(1))
    put(bounds._length_key(array.binding_id), bounds.Interval.exact(0))
    store(array, value, 'first')
    validator._read_element(state, array.binding_id, result.binding_id, LOC)
    checks.append(f'    elements.read(@state {array.binding_id} {result.binding_id} {word} span @registry)')
    snapshot('read')
    validator._copy_element_facts(state, array.binding_id, copied.binding_id, LOC)
    checks.append(f'    elements.copy(@state {array.binding_id} {copied.binding_id} {word} span @registry)')
    snapshot('copy')
    put(bounds._length_key(array.binding_id), bounds.Interval.exact(1))
    put(remainder, bounds.Interval(-1, None))
    store(array, value, 'weaken')
    store(array, unknown, 'drop')
    put(bounds._length_key(array.binding_id), bounds.Interval.exact(0))
    store(array, value, 'empty')
    put(bounds._length_key(scalars.binding_id), bounds.Interval.exact(0))
    store(scalars, start, 'scalar')
    validator._read_element(state, scalars.binding_id, scalar_result.binding_id, LOC)
    checks.append(f'    elements.read(@state {scalars.binding_id} {scalar_result.binding_id} {word} span @registry)')
    snapshot('scalar-read')
    for index, node in enumerate([value, result, read, member, unknown]):
        sources = validator._value_fact_sources(node)
        checks.append(f'    emit_sources("sources{index}" elements.sources({names[id(node)]} env @registry))')
        expected.extend(f'sources{index}|{"/".join(path)}|{id}' for path, id in sources)
        route = validator._element_route_of(node)
        checks.append(f'    emit_route("route{index}" elements.route_of({names[id(node)]} env @registry))')
        expected.append(f'route{index}|{route}')
    source = tmp_path / 'element_facts.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/value_bounds.dewy'}" as values
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/element_facts.dewy'}" as elements
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as flow
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
emit = (label:string state:flow.State):>void => {{
    loop entry in state.values {{
        let lo = if entry.interval.lower is? none '-' else _bigint_as_string(entry.interval.lower)
        let hi = if entry.interval.upper is? none '+' else _bigint_as_string(entry.interval.upper)
        printl("{{label}}|{{entry.fact.key}}|{{lo}},{{hi}},{{entry.interval.capped}}")
    }}
}}
emit_sources = (label:string sources:array<elements.Source>):>void => {{
    loop source in sources {{ printl("{{label}}|{{source.path.join('/')}}|{{source.binding}}") }}
}}
emit_route = (label:string route:addr?):>void => {{
    let value = if route is? none 'None' else "{{route}}"
    printl("{{label}}|{{value}}")
}}
main = ():>int64 => {{
    let span = Span[0 0]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let registry = bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env = values.Environment[nodes type_nodes registry {validator.max_length}]
    let state:flow.State = []
{chr(10).join(checks)}
    let contract = elements.declared_refinement({refined.binding_id} type_nodes registry)
    $runtime_assert contract isnt? none and contract.propositions.length =? 1
    let roots = elements.roots(registry)
    loop route in registry.routes {{
        if route.path.length >? 0 and route.path[0] =? '*' {{
            $runtime_assert route.id in? roots and roots[route.id] =? route.root
        }}
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert sorted(result.stdout.splitlines()) == sorted(expected)
