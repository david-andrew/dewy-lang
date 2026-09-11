"""The native predicate driver connects paths, comparisons, and call contracts."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_predicate_fact_driver(tmp_path):
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('props', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('predicates', 'analyze/predicate_facts.dewy'),
        ('facts', 'analyze/fact_state.dewy'), ('ranges', 'analyze/intervals.dewy'),
        ('intervals', 'analyze/expression_intervals.dewy'), ('relations', 'analyze/relations.dewy'),
    ])
    source = tmp_path / 'predicate_facts.dewy'
    source.write_text(f'''from reporting import Span
{imports}
main=():>int64=>{{
    let span=Span[0 0]
    let type_nodes:array<types.Type>=[]
    let word=types.primitive('int64' @type_nodes)
    let boolean=types.primitive('bool' @type_nodes)
    let string=types.primitive('string' @type_nodes)
    let absent=types.primitive('none' @type_nodes)
    let comparison=types.function_type([types.PosOrKwArg['a' word] types.PosOrKwArg['b' word]] [] none boolean [] @type_nodes)
    let nodes:array<hir.AST>=[]
    let i=hir.append_node(@nodes hir.ExpressedIdentifier[span word 'i' 1])
    let j=hir.append_node(@nodes hir.ExpressedIdentifier[span word 'j' 2])
    let text=hir.append_node(@nodes hir.ExpressedIdentifier[span string 'text' 3])
    let length=hir.append_node(@nodes hir.StringLength[span word text])
    let le=hir.append_node(@nodes hir.ExpressedIdentifier[span comparison '__le__'])
    let lt=hir.append_node(@nodes hir.ExpressedIdentifier[span comparison '__lt__'])
    let first=hir.append_node(@nodes hir.FunctionCall[span boolean le [i j] []])
    let last=hir.append_node(@nodes hir.FunctionCall[span boolean lt [j length] []])
    let condition=hir.append_node(@nodes hir.ShortCircuit[span boolean 'and' first last])
    let promised=types.refined_type(boolean [props.Proposition['@src' '>=?' 3 projection='length' when=true]] @type_nodes)
    let signature=types.function_type([types.PosOrKwArg['src' string]] [] none promised [] @type_nodes)
    let predicate=hir.append_node(@nodes hir.ExpressedIdentifier[span signature 'has_prefix'])
    let called=hir.append_node(@nodes hir.FunctionCall[span boolean predicate [text] []])
    let payload=types.refined_type(word [props.Proposition['self' '>=?' 0] props.Proposition['@src' '>=?' 1 projection='length']] @type_nodes)
    let returned=types.union([payload absent] @type_nodes)
    let result_type=types.union([word absent] @type_nodes)
    let measure_type=types.function_type([types.PosOrKwArg['src' string]] [] none returned [] @type_nodes)
    let measure=hir.append_node(@nodes hir.ExpressedIdentifier[span measure_type 'measure'])
    let measured=hir.append_node(@nodes hir.FunctionCall[span result_type measure [text] []])
    let ordinary_type=types.function_type([types.PosOrKwArg['src' string]] [] none result_type [] @type_nodes)
    let ordinary=hir.append_node(@nodes hir.ExpressedIdentifier[span ordinary_type 'ordinary'])
    let unpromised=hir.append_node(@nodes hir.FunctionCall[span result_type ordinary [text] []])
    let result=hir.append_node(@nodes hir.ExpressedIdentifier[span result_type 'result' 4])
    let selected=hir.append_node(@nodes hir.TypeTest[span boolean result absent true])
    let registry=bindings.Registry[]
    registry.by_id[1]=bindings.Binding[1 'i' 'value' span value_type=word]
    registry.by_id[2]=bindings.Binding[2 'j' 'value' span value_type=word]
    registry.by_id[3]=bindings.Binding[3 'text' 'value' span value_type=string]
    registry.by_id[4]=bindings.Binding[4 'result' 'value' span value_type=result_type]
    let env=values.Environment[nodes type_nodes registry 1024]
    let state:facts.State=[]
    facts.set_value(@state facts.Term[1] ranges.Interval[0 100])
    facts.set_value(@state facts.Term[2] ranges.Interval[0 100])
    facts.set_value(@state facts.Term[3 'length'] ranges.Interval[5 10])
    let snapshot=intervals.Snapshot[]
    loop id in 0.. and id <? nodes.length {{intervals.record(@snapshot id state env @registry)}}
    let data=predicates.Data[env relations.Context[facts.Context[1024]] snapshot registry member_calls=[4 -> measured]]
    let refined=predicates.refine(state condition true @data)
    $runtime_assert refined isnt? none
    $runtime_assert facts.index(1 3).key in? refined and facts.index(2 3).key in? refined
    let bound=facts.lookup(refined facts.value(facts.Term[1]))
    $runtime_assert bound isnt? none and bound.lower =? 0 and bound.upper =? 9
    # Invalidate the named evidence while retaining the already read value.
    intervals.forget(@data.snapshot 1)
    facts.set_value(@state facts.Term[1] ranges.exact(99))
    refined=predicates.refine(state condition true @data)
    $runtime_assert refined isnt? none
    $runtime_assert facts.index(1 3).key not in? refined
    bound=facts.lookup(refined facts.value(facts.Term[1]))
    $runtime_assert bound isnt? none and bound.lower =? 99
    state.clear
    snapshot=intervals.Snapshot[]
    loop id in 0.. and id <? nodes.length {{intervals.record(@snapshot id state env @registry)}}
    data.snapshot=snapshot
    refined=predicates.refine(state called true @data)
    $runtime_assert refined isnt? none
    bound=facts.lookup(refined facts.value(facts.Term[3 'length']))
    $runtime_assert bound isnt? none and bound.lower =? 3
    refined=predicates.refine(state called false @data)
    $runtime_assert refined isnt? none
    $runtime_assert facts.value(facts.Term[3 'length']).key not in? refined
    refined=predicates.refine(state selected true @data)
    $runtime_assert refined isnt? none
    bound=facts.lookup(refined facts.value(facts.Term[3 'length']))
    $runtime_assert bound isnt? none and bound.lower =? 1
    bound=facts.lookup(refined facts.value(facts.Term[4]))
    $runtime_assert bound isnt? none and bound.lower =? 0
    # An ordinary optional result has no conditional return contract. Neither
    # branch establishes a new argument-length or result-value promise.
    data.member_calls[4]=unpromised
    loop truth in [true false] {{
        refined=predicates.refine(state selected truth @data)
        $runtime_assert refined isnt? none
        $runtime_assert facts.value(facts.Term[3 'length']).key not in? refined
        $runtime_assert facts.value(facts.Term[4]).key not in? refined
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
