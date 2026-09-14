"""Direct contract comparison preserves identity without formatting keys."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_proposition_comparison_matches_structural_keys(tmp_path):
    source = f'''
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
''' + BODY
    path = tmp_path / 'propositions.dewy'
    path.write_text(source)
    execute(tmp_path, 'propositions', codegen(SrcFile.from_path(path), debug_locations=False))


BODY = '''
main=():>int64=>{
    let nodes:array<types.Type>=[]
    let word=types.primitive('int64' @nodes)
    let first=types.object_type([types.ObjectField['value' word default=1]] none false [] [] @nodes)
    let second=types.object_type([types.ObjectField['value' word default=2]] none false [] [] @nodes)
    if first =? second or not types.same_type(first second nodes) return 1
    let base=facts.Proposition['self' '=?']
    let provenance=facts.Proposition['self' '=?' term_id=7 subject_id=9]
    if not types.same_proposition(base provenance nodes) return 2
    let tested=facts.Proposition['self' 'is?' tested_type=first]
    let equivalent=facts.Proposition['self' 'is?' tested_type=second]
    if not types.same_proposition(tested equivalent nodes) return 3
    let different:array<facts.Proposition>=[
        facts.Proposition['length' '=?']
        facts.Proposition['self' 'not=?']
        facts.Proposition['self' '=?' value=18446744073709551616]
        facts.Proposition['self' '=?' value=-1]
        facts.Proposition['self' '=?' projection='length']
        facts.Proposition['self' '=?' term='none']
        facts.Proposition['self' '=?' term='x:;"']
        facts.Proposition['self' '=?' term_projection='value']
        facts.Proposition['self' '=?' tested_type=word]
        facts.Proposition['self' '=?' when=true]
        facts.Proposition['self' '=?' when=false]
        facts.Proposition['self' '=?' axiom='none']
    ]
    loop other in different {if types.same_proposition(base other nodes) return 4}
    let all=different
    all.push(base) all.push(provenance) all.push(tested) all.push(equivalent)
    loop left in all {loop right in all {
        let expected=types.propositions_key([left] true nodes) =? types.propositions_key([right] true nodes)
        if types.same_proposition(left right nodes) not=? expected return 5
    }}
    let before:int64=_arena_allocated_bytes
    loop i in 0.. and i <? 100 {
        if not types.same_proposition(tested equivalent nodes) return 6
    }
    let direct:int64=_arena_allocated_bytes-before
    before=_arena_allocated_bytes
    loop i in 0.. and i <? 100 {
        if types.propositions_key([tested] true nodes) not=? types.propositions_key([equivalent] true nodes) return 7
    }
    let formatted:int64=_arena_allocated_bytes-before
    printl("{direct} {formatted}")
    if direct*4 >=? formatted return 8
    return 42
}
'''
