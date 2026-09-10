"""Short-circuit evidence describes surviving values, including across writes."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_short_circuit_proof_paths(tmp_path):
    module = ROOT / 'dewy/bootstrap/semantic/analyze'
    source = tmp_path / 'paths.dewy'
    source.write_text(f'''from reporting import Span
import p"{module.parent / 'hir.dewy'}" as hir
import p"{module / 'predicate_paths.dewy'}" as paths
import p"{module / 'fact_state.dewy'}" as facts
import p"{module / 'intervals.dewy'}" as ranges
leaf=(state:facts.State condition:addr truth:bool context:paths.Context @data:bool):>facts.State?=>{{
        data=true
        let node=hir.node_at(context.nodes condition)
        if node is? hir.Block {{
            $runtime_assert node.items.length >? 0
            node=hir.node_at(context.nodes node.items[node.items.length-1])
    }}
        $runtime_assert node is? hir.ExpressedIdentifier and node.binding_id isnt? none
        let result=state
        let key=facts.value(facts.Term[node.binding_id])
        let old=facts.lookup(result key)
        let desired=ranges.exact(if truth 1 else 0)
        if old isnt? none {{desired=ranges.intersect(desired old)}}
        if ranges.is_empty(desired) return none
        facts.put(@result key desired)
        return result
}}
main=():>int64=>{{
    let span=Span[0 0]
    let nodes:array<hir.AST>=[]
    let a=hir.append_node(@nodes hir.ExpressedIdentifier[span 0 'a' 1])
    let b=hir.append_node(@nodes hir.ExpressedIdentifier[span 0 'b' 2])
    let no=hir.append_node(@nodes hir.Bool[span 0 false])
    let write=hir.append_node(@nodes hir.Assign[span 0 a '=' no])
    let later=hir.append_node(@nodes hir.Block[span 0 [write b] true])
    let chain=hir.append_node(@nodes hir.ShortCircuit[span 0 'and' a later])
    let impossible=hir.append_node(@nodes hir.ShortCircuit[span 0 'and' a no])
    let context=paths.Context[nodes facts.Context[cap=100]]
    let state:facts.State=[]
    let visited=false
    let invalidated:set<addr>=set[]
    let result=paths.refine(state chain true invalidated context @visited @leaf)
    $runtime_assert visited
    $runtime_assert result isnt? none
    $runtime_assert facts.value(facts.Term[1]).key not in? result
    let second=facts.lookup(result facts.value(facts.Term[2]))
    $runtime_assert second isnt? none and second.lower =? 1 and second.upper =? 1
    $runtime_assert paths.refine(state impossible true invalidated context @visited @leaf) is? none
    let operations:array<'and'|'or'|'nand'|'nor'>=['and' 'or' 'nand' 'nor']
    loop op in operations {{
        let id=hir.append_node(@nodes hir.ShortCircuit[span 0 op a b])
        let updated=paths.Context[nodes facts.Context[cap=100]]
        loop truth in [false true] {{
            let refined=paths.refine(state id truth invalidated updated @visited @leaf)
            $runtime_assert refined isnt? none
            let left=facts.lookup(refined facts.value(facts.Term[1]))
            let right=facts.lookup(refined facts.value(facts.Term[2]))
            printl("{{op}} {{truth}} {{if left is? none 0 else left.lower}} {{if left is? none 1 else left.upper}} {{if right is? none 0 else right.lower}} {{if right is? none 1 else right.upper}}")
        }}
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = result.stdout.splitlines()
    assert len(rows) == 8
    for line in rows:
        op, truth, *bounds = line.split()
        al, ah, bl, bh = map(int, bounds)
        for a in (False, True):
            for b in (False, True):
                value = (a and b) if op in ('and', 'nand') else (a or b)
                if op in ('nand', 'nor'):
                    value = not value
                if value == (truth == 'true'):
                    assert al <= int(a) <= ah and bl <= int(b) <= bh, (line, a, b)
