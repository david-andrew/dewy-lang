"""Stored values retain facts independently of their former storage."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_binding_fact_transfer(tmp_path):
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('props', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('predicates', 'analyze/predicate_facts.dewy'),
        ('facts', 'analyze/fact_state.dewy'), ('ranges', 'analyze/intervals.dewy'),
        ('intervals', 'analyze/expression_intervals.dewy'), ('relations', 'analyze/relations.dewy'),
        ('stores', 'analyze/binding_facts.dewy'), ('refinements', 'analyze/refinement_facts.dewy'),
    ])
    source = tmp_path / 'binding_facts.dewy'
    source.write_text(f'''from reporting import Span
{imports}
main=():>int64=>{{
    let span=Span[0 0]
    let type_nodes:array<types.Type>=[]
    let word=types.primitive('int64' @type_nodes)
    let string=types.primitive('string' @type_nodes)
    let record=types.object_type([types.ObjectField['count' word] types.ObjectField['text' string]] none false [] [] @type_nodes)
    let promised=types.refined_type(word [props.Proposition['self' '<=?' term='src']] @type_nodes)
    let function=types.function_type([types.PosOrKwArg['src' string]] [] none promised [] @type_nodes)
    let nodes:array<hir.AST>=[]
    let i=hir.append_node(@nodes hir.ExpressedIdentifier[span word 'i' 1])
    let text=hir.append_node(@nodes hir.ExpressedIdentifier[span string 'text' 2])
    let length=hir.append_node(@nodes hir.StringLength[span word text])
    let seven=hir.append_node(@nodes hir.Integer[span word '0d' 7])
    let literal=hir.append_node(@nodes hir.ObjectLiteral[span record [hir.ObjectField[span 'count' seven] hir.ObjectField[span 'text' text]]])
    let f=hir.append_node(@nodes hir.ExpressedIdentifier[span function 'measure'])
    let called=hir.append_node(@nodes hir.FunctionCall[span word f [text] []])
    let registry=bindings.Registry[]
    registry.by_id[1]=bindings.Binding[1 'i' 'value' span value_type=word]
    registry.by_id[2]=bindings.Binding[2 'text' 'value' span value_type=string]
    # Allocate destination ids through the registry so projected routes
    # cannot accidentally collide with the fixture's explicit ids.
    registry.next_id=10
    let copy=bindings.allocate(@registry none 'copy' 'value' span)
    let size=bindings.allocate(@registry none 'size' 'value' span)
    let object=bindings.allocate(@registry none 'object' 'value' span)
    let result=bindings.allocate(@registry none 'result' 'value' span)
    let state:facts.State=[]
    facts.set_value(@state facts.Term[1] ranges.Interval[1 4])
    facts.set_value(@state facts.Term[2 'length'] ranges.Interval[5 9])
    facts.put(@state facts.index(1 2) ranges.exact(1))
    let env=values.Environment[nodes type_nodes registry 1024]
    let snapshot=intervals.Snapshot[]
    loop id in 0.. and id <? nodes.length {{intervals.record(@snapshot id state env @registry)}}
    let data=predicates.Data[env relations.Context[facts.Context[1024]] snapshot registry]
    let declared:refinements.Declared=[]
    stores.install(@state copy text none word span @declared @data)
    stores.install(@state size length none word span @declared @data)
    stores.install(@state object literal record word span @declared @data)
    stores.install(@state result called none word span @declared @data)
    $runtime_assert facts.index(1 copy).key in? state
    $runtime_assert relations.ordered(facts.Term[size] facts.Term[2 'length'] 0 state data.relations)
    $runtime_assert relations.ordered(facts.Term[2 'length'] facts.Term[size] 0 state data.relations)
    $runtime_assert relations.ordered(facts.Term[result] facts.Term[2 'length'] 0 state data.relations)
    let count=bindings.route_id(@data.registry object ['count'] word span)
    let field_text=bindings.route_id(@data.registry object ['text'] string span)
    let bound=facts.lookup(state facts.value(facts.Term[count]))
    $runtime_assert bound isnt? none and bound.lower =? 7 and bound.upper =? 7
    bound=facts.lookup(state facts.value(facts.Term[field_text 'length']))
    $runtime_assert bound isnt? none and bound.lower =? 5 and bound.upper =? 9
    # Mutating just one field loses that field's evidence, not its sibling.
    stores.forget(@state object @data prefix=['count'])
    $runtime_assert facts.value(facts.Term[count]).key not in? state
    $runtime_assert facts.value(facts.Term[field_text 'length']).key in? state
    # Replacing the source preserves the independent copy's index proof.
    stores.forget(@state 2 @data)
    $runtime_assert facts.index(1 2).key not in? state and facts.index(1 copy).key in? state
    bound=facts.lookup(state facts.value(facts.Term[copy 'length']))
    $runtime_assert bound isnt? none and bound.lower =? 5 and bound.upper =? 9
    stores.forget(@state object @data)
    $runtime_assert facts.value(facts.Term[field_text 'length']).key not in? state
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
