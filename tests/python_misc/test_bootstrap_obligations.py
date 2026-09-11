"""Only established evidence discharges native refinement obligations."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_obligation_discharge(tmp_path):
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('props', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('predicates', 'analyze/predicate_facts.dewy'),
        ('facts', 'analyze/fact_state.dewy'), ('ranges', 'analyze/intervals.dewy'),
        ('intervals', 'analyze/expression_intervals.dewy'), ('relations', 'analyze/relations.dewy'),
        ('obligations', 'analyze/obligations.dewy'), ('paths', 'analyze/predicate_paths.dewy'),
    ])
    source = tmp_path / 'obligations.dewy'
    source.write_text(f'''from reporting import Span, SrcFile
{imports}
main=():>int64=>{{
    let span=Span[0 0]
    let type_nodes:array<types.Type>=[]
    let word=types.primitive('int64' @type_nodes)
    let boolean=types.primitive('bool' @type_nodes)
    let string=types.primitive('string' @type_nodes)
    let record=types.object_type([types.ObjectField['count' word refinement=[props.Proposition['self' '>=?' 3]]]] none false [] [] @type_nodes)
    let positive=types.refined_type(word [props.Proposition['self' '>?' 0]] @type_nodes)
    let conditional=types.refined_type(boolean [props.Proposition['@text' '>?' 100 projection='length' subject_id=2 when=true]] @type_nodes)
    let nodes:array<hir.AST>=[]
    let i=hir.append_node(@nodes hir.ExpressedIdentifier[span word 'i' 1])
    let text=hir.append_node(@nodes hir.ExpressedIdentifier[span string 'text' 2])
    let object=hir.append_node(@nodes hir.ExpressedIdentifier[span record 'object' 3])
    let seven=hir.append_node(@nodes hir.Integer[span word '0d' 7])
    let literal=hir.append_node(@nodes hir.ObjectLiteral[span record [hir.ObjectField[span 'count' seven]]])
    let no=hir.append_node(@nodes hir.Bool[span boolean false])
    let yes=hir.append_node(@nodes hir.Bool[span boolean true])
    let registry=bindings.Registry[]
    registry.by_id[1]=bindings.Binding[1 'i' 'value' span value_type=word]
    registry.by_id[2]=bindings.Binding[2 'text' 'value' span value_type=string]
    registry.by_id[3]=bindings.Binding[3 'object' 'value' span value_type=record]
    let env=values.Environment[nodes type_nodes registry 1024]
    let state:facts.State=[]
    facts.set_value(@state facts.Term[1] ranges.Interval[3 7])
    facts.set_value(@state facts.Term[2 'length'] ranges.Interval[8 10])
    let snapshot=intervals.Snapshot[]
    loop id in 0.. and id <? nodes.length {{intervals.record(@snapshot id state env @registry)}}
    let data=predicates.Data[env relations.Context[facts.Context[1024]] snapshot registry]
    let assigned:set<addr>=set[]
    $runtime_assert obligations.verdict(props.Proposition['self' '>?' 0] i state assigned @data) =? true
    $runtime_assert obligations.verdict(props.Proposition['self' '<?' 0] i state assigned @data) =? false
    $runtime_assert obligations.verdict(props.Proposition['self' '=?' 5] i state assigned @data) is? none
    $runtime_assert obligations.verdict(props.Proposition['self' '<?' term='text' term_id=2] i state assigned @data) =? true
    $runtime_assert obligations.verdict(props.Proposition['length' '>=?' 8] text state assigned @data) =? true
    $runtime_assert obligations.verdict(props.Proposition['.count' '>=?' 3] object state assigned @data) =? true
    $runtime_assert obligations.verdict(props.Proposition['.count' '=?' 7] literal state assigned @data) =? true
    $runtime_assert obligations.verdict(props.Proposition['.count' '=?' 3] literal state assigned @data) =? false
    # A forgotten identity cannot import the replacement's bounds into the
    # saved argument. The already observed interval is still usable.
    intervals.forget(@data.snapshot 1)
    facts.set_value(@state facts.Term[1] ranges.exact(99))
    $runtime_assert obligations.verdict(props.Proposition['self' '<=?' 7] i state assigned @data) =? true
    $runtime_assert obligations.verdict(props.Proposition['self' '=?' 99] i state assigned @data) =? false
    let src=SrcFile[path='<obligation test>' body='']
    let context=paths.Context[data.env.nodes data.relations.facts]
    $runtime_assert obligations.check(hir.Obligation[span word i positive 'positive argument'] state assigned src context @data) is? none
    # A conditional promise is vacuous on an impossible result path; it is
    # still refuted when that result is possible and the promise is false.
    $runtime_assert obligations.check(hir.Obligation[span boolean no conditional 'conditional result'] state assigned src context @data) is? none
    let failed=obligations.check(hir.Obligation[span boolean yes conditional 'conditional result'] state assigned src context @data)
    $runtime_assert failed isnt? none and failed.title =? 'refinement refuted'
    let unknown=types.refined_type(word [props.Proposition['self' '=?' 5]] @type_nodes)
    data.env=values.Environment[nodes type_nodes registry 1024]
    failed=obligations.check(hir.Obligation[span word i unknown 'unknown value'] state assigned src context @data)
    $runtime_assert failed isnt? none and failed.title =? 'cannot prove refinement'
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
