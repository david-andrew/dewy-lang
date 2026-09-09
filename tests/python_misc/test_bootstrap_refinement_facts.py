"""Native contracts seed value, length, field, and immutable sibling facts."""

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


def test_native_refinement_facts_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()

    def reference(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    sequence = reference('sequence', ty.StringType(None))
    p = ty.Proposition
    numeric = ty.ObjectType((ty.ObjectField('sign', 'int8'), ty.ObjectField('limbs', ty.ArrayType('uint64', None))))
    record = ty.ObjectType((ty.ObjectField('denominator', numeric), ty.ObjectField('text', ty.StringType(None)), ty.ObjectField('position', 'uint64')))
    contracts = [
        ty.RefinedType('int64', (p('self', '>=?', 3), p('self', '<=?', 7), p('self', 'not=?', 0))),
        ty.RefinedType('int64', (p('self', '<?', 0, term='sequence', term_id=sequence.binding_id), p('self', '>=?', 0))),
        ty.RefinedType(ty.StringType(None), (p('length', '>=?', 2), p('length', '<=?', 8))),
        ty.RefinedType(record, (p('.denominator.sign', '>?', 0), p('.denominator.sign', 'not=?', 0),
                                p('.text', '>=?', 2, of='length'), p('.position', '>=?', 0, axiom='addr'))),
        ty.RefinedType('int64', (p('self', '=?', 0, term='value', term_id=2, term_of='value'),)),
        ty.addr_type(),
        ty.RefinedType(ty.ArrayType('int64', None), (p('length', '<=?', 0, term='sequence', term_id=sequence.binding_id),)),
    ]
    references = [reference(f'v{i}', contract) for i, contract in enumerate(contracts)]
    fields = (ty.ObjectField('alphabet', ty.StringType(None), refinement=(p('length', '>=?', 2), p('length', '<=?', 255))),
              ty.ObjectField('radix', 'uint8', refinement=(p('self', '=?', 0, term='alphabet'),)),
              ty.ObjectField('quantity', 'int', refinement=(p('self', '>=?', 0, term='limit', term_of='value'),)),
              ty.ObjectField('limit', 'int64'))
    immutable = ty.ObjectType(fields, immutable=True)
    mutable = ty.ObjectType(fields)
    info = reference('info', immutable)
    changed = reference('changed', mutable)
    nested_type = ty.ObjectType((ty.ObjectField('info', immutable),))
    outer = reference('outer', nested_type)
    nested = hir.MemberAccess(LOC, immutable, outer, 'info')
    members = [hir.MemberAccess(LOC, 'uint8', info, 'radix'),
               hir.MemberAccess(LOC, ty.StringType(None), info, 'alphabet'),
               hir.MemberAccess(LOC, 'uint8', changed, 'radix'),
               hir.MemberAccess(LOC, 'uint8', nested, 'radix'),
               hir.MemberAccess(LOC, 'int', info, 'quantity')]
    # Positional and keyword-only contracts share the same seeding rule.
    function = hir.FunctionLiteral(LOC, ty.FunctionType([], [], None, 'void'),
                                   [hir.Param('arg', references[0].type, binding_id=references[0].binding_id)],
                                   [hir.Param('kw', references[2].type, binding_id=references[2].binding_id)],
                                   None, 'void', hir.Block(LOC, 'void', [], False))
    root = hir.Block(LOC, 'void', [sequence, *references, *members, function], False)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root)
    validator.max_length = 1024
    base_bindings = list(registry.by_id.values())
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    word = build('int64')
    registry_lines = [f'    registry.by_id[{b.id}] = bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]'
                      for b in base_bindings]
    state, checks, expected = {}, [], []

    def snapshot(label):
        checks.append(f'    emit("{label}" state)')
        expected.extend(f'{label}|{fact(key)[1]}|{spelling(value)}' for key, value in state.items())

    for index, node in enumerate(references):
        refined = node.type
        assert isinstance(refined, ty.RefinedType)
        validator._seed_binding_refinement(node.binding_id, refined, state, LOC)
        checks.append(f'''    let refined{index} = types.node_at(type_nodes {build(refined)})
    $runtime_assert refined{index} is? types.RefinedType
    refinements.seed_binding(@state @declared {node.binding_id} refined{index} context span @registry)''')
        snapshot(f'binding{index}')
    for index, node in enumerate(members):
        validator._seed_sibling_relations(node, state)
        checks.append(f'''    let member{index} = hir.node_at(nodes {names[id(node)]})
    $runtime_assert member{index} is? hir.MemberAccess
    refinements.seed_siblings(@state member{index} env @registry)''')
        snapshot(f'sibling{index}')
        interval = validator._field_declared_interval(node, state)
        checks.append(f'    emit_interval("field{index}" refinements.field_interval(member{index} state env @registry))')
        expected.append(f'field{index}|none' if interval is None else f'field{index}|{spelling(interval)}')
    state = {}
    validator._seed_parameter_refinements(function, state)
    checks.append(f'''    state.clear
    let function = hir.node_at(nodes {names[id(function)]})
    $runtime_assert function is? hir.FunctionLiteral
    refinements.seed_parameters(@state @declared function context @registry)''')
    snapshot('parameters')
    source = tmp_path / 'refinement_facts.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/value_bounds.dewy'}" as values
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/refinement_facts.dewy'}" as refinements
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as flow
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
emit_interval = (label:string interval:ranges.Interval?):>void => {{
    if interval is? none {{ printl("{{label}}|none") }}
    else {{
        let lo = if interval.lower is? none '-' else _bigint_as_string(interval.lower)
        let hi = if interval.upper is? none '+' else _bigint_as_string(interval.upper)
        printl("{{label}}|{{lo}},{{hi}},{{interval.capped}}")
    }}
}}
emit = (label:string state:flow.State):>void => {{
    loop entry in state.values {{
        let lo = if entry.interval.lower is? none '-' else _bigint_as_string(entry.interval.lower)
        let hi = if entry.interval.upper is? none '+' else _bigint_as_string(entry.interval.upper)
        printl("{{label}}|{{entry.fact.key}}|{{lo}},{{hi}},{{entry.interval.capped}}")
    }}
}}
main = ():>int64 => {{
    let span = Span[0 0]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let registry = bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env = values.Environment[nodes type_nodes registry 1024]
    let context = refinements.Context[env {word}]
    let declared:refinements.Declared = []
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
