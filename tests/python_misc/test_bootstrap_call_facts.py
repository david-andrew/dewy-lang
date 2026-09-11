"""Selected result contracts become facts about actual argument routes."""

import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)


def test_native_call_argument_promises(tmp_path):
    registry = bindings.BindingRegistry()

    def ref(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    text = ref('text', 'string')
    i = ref('i', 'int64')
    flag = ref('flag', 'bool')
    literal = hir.String(LOC, ty.StringLiteralType('abc'), 'abc')
    window = hir.StringSlice(LOC, 'string', text, hir.Range(LOC, 'range', '[)', None, i, None))

    def call(args, proposition):
        result = ty.RefinedType('bool', (proposition,))
        signature = ty.FunctionType([ty.PosOrKwArg(name, value.type, True) for name, value in args], [], None, result)
        function = hir.ExpressedIdentifier(LOC, signature, 'predicate')
        return hir.FunctionCall(LOC, 'bool', function, [value for _, value in args], {})

    calls = [
        call([('value', i)], ty.Proposition('@value', '>=?', 3)),
        call([('value', i), ('src', text)], ty.Proposition('@value', '<?', 0, term='src', when=True)),
        call([('prefix', literal), ('src', window)], ty.Proposition('@prefix', '<=?', 0, of='length', term='src', when=True)),
        call([('ok', flag)], ty.Proposition('@ok', '=?', 1, when=True)),
    ]
    root = hir.Block(LOC, 'void', calls, False)
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    registry_lines = [f'    registry.by_id[{b.id}]=bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]'
                      for b in registry.by_id.values()]
    source = tmp_path / 'call_facts.dewy'
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('facts', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('calls', 'analyze/call_facts.dewy'),
        ('flow', 'analyze/fact_state.dewy'), ('ranges', 'analyze/intervals.dewy'),
        ('intervals', 'analyze/expression_intervals.dewy'), ('relations', 'analyze/relations.dewy'),
        ('terms', 'analyze/term_facts.dewy'),
    ])
    source.write_text(f'''from reporting import Span
{imports}
main=():>int64=>{{
    let span=Span[0 0]
    let nodes:array<hir.AST>=[]
    let type_nodes:array<types.Type>=[]
    let registry=bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env=values.Environment[nodes type_nodes registry 1024]
    let snapshot=intervals.Snapshot[]
    snapshot.numbers[{names[id(i)]}]=ranges.Interval[0 8]
    snapshot.lengths[{names[id(text)]}]=ranges.Interval[10 20]
    snapshot.lengths[{names[id(window)]}]=ranges.Interval[2 20]
    snapshot.lengths[{names[id(literal)]}]=ranges.exact(3)
    snapshot.terms[{names[id(i)]}]=terms.Offset[flow.Term[{i.binding_id}] 0]
    snapshot.terms[{names[id(text)]}]=terms.Offset[flow.Term[{text.binding_id}] 0]
    snapshot.terms[{names[id(flag)]}]=terms.Offset[flow.Term[{flag.binding_id}] 0]
    snapshot.sequences[{names[id(text)]}]={text.binding_id}
    let relation=relations.Context[flow.Context[1024]]
    let initial:flow.State=[]
    flow.set_value(@initial flow.Term[{i.binding_id}] ranges.Interval[0 8])
    let result=calls.apply(initial {names[id(calls[0])]} none env relation snapshot @registry)
    $runtime_assert result.state isnt? none
    let value=flow.lookup(result.state flow.value(flow.Term[{i.binding_id}]))
    $runtime_assert value isnt? none and value.lower =? 3 and value.upper =? 8
    result=calls.apply(initial {names[id(calls[1])]} false env relation snapshot @registry)
    $runtime_assert result.state isnt? none
    $runtime_assert flow.index({i.binding_id} {text.binding_id}).key not in? result.state
    result=calls.apply(initial {names[id(calls[1])]} true env relation snapshot @registry)
    $runtime_assert result.state isnt? none
    $runtime_assert flow.index({i.binding_id} {text.binding_id}).key in? result.state
    result=calls.apply(initial {names[id(calls[2])]} true env relation snapshot @registry)
    $runtime_assert result.state isnt? none
    let gap=flow.lookup(result.state flow.order(flow.Term[{i.binding_id}] flow.Term[{text.binding_id} 'length']))
    $runtime_assert gap isnt? none and gap.lower =? 3
    result=calls.apply(initial {names[id(calls[3])]} true env relation snapshot @registry)
    $runtime_assert result.conditions.length =? 1
    $runtime_assert result.conditions[0].expression =? {names[id(flag)]} and result.conditions[0].truth
    result=calls.apply(initial {names[id(calls[3])]} none env relation snapshot @registry)
    $runtime_assert result.conditions.length =? 0
    # A later argument write changes the current binding, not the earlier
    # value argument. Its result promise must not constrain that replacement.
    intervals.forget(@snapshot {i.binding_id})
    intervals.forget(@snapshot {flag.binding_id})
    result=calls.apply(initial {names[id(calls[1])]} true env relation snapshot @registry)
    $runtime_assert result.state isnt? none
    $runtime_assert flow.index({i.binding_id} {text.binding_id}).key not in? result.state
    result=calls.apply(initial {names[id(calls[2])]} true env relation snapshot @registry)
    $runtime_assert result.state isnt? none
    $runtime_assert flow.order(flow.Term[{i.binding_id}] flow.Term[{text.binding_id} 'length']).key not in? result.state
    result=calls.apply(initial {names[id(calls[3])]} true env relation snapshot @registry)
    $runtime_assert result.conditions.length =? 0
    flow.set_value(@initial flow.Term[{i.binding_id}] ranges.exact(1))
    snapshot.numbers[{names[id(i)]}]=ranges.exact(1)
    result=calls.apply(initial {names[id(calls[0])]} none env relation snapshot @registry)
    $runtime_assert result.state is? none
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
