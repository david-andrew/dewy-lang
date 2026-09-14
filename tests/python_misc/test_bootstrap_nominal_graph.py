"""Nominal closure stays with the graph through late edges, forks, and cycles."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
BODY = '''
# Independent reachability oracle: the previous edge-scanning implementation.
reachable=(child:string parent:string edges:array<subtyping.Link>):>bool=>{
    if child =? parent return true
    let pending:array<string>=[child]
    let seen:set<string>=set[child]
    loop pending.length >? 0 {
        let current=pending.pop
        loop edge in edges {
            if edge.child not=? current continue
            if edge.parent =? parent return true
            if edge.parent not in? seen {seen.add(edge.parent) pending.push(edge.parent)}
        }
    }
    return false
}
agrees=(graph:subtyping.Graph):>bool=>{
    loop child in ['a' 'b' 'c' 'd' 'e' 'unknown'] {
        loop parent in ['a' 'b' 'c' 'd' 'e' 'unknown'] {
            if subtyping.nominal_subtype(child parent graph) not=? reachable(child parent graph.edges) return false
        }
    }
    return true
}
measure=(cached:bool graph:subtyping.Graph):>int64=>{
    let before:int64=_arena_allocated_bytes
    loop i in 0.. and i <? 128 {
        let yes=if cached subtyping.nominal_subtype('int8' 'number' graph) else reachable('int8' 'number' graph.edges)
        let no=if cached subtyping.nominal_subtype('int8' 'string' graph) else reachable('int8' 'string' graph.edges)
        if not yes or no return -1
    }
    return _arena_allocated_bytes-before
}
main=():>int64=>{
    let graph=subtyping.Graph[]
    let additions:array<subtyping.Link>=[['b' 'c'] ['a' 'b'] ['d' 'e'] ['c' 'd'] ['e' 'a'] ['c' 'a'] ['a' 'a']]
    loop edge in additions {
        subtyping.add_link(@graph edge)
        if not agrees(graph) return 1
    }
    let snapshot=graph
    subtyping.add_link(@graph subtyping.Link['e' 'new'])
    if not subtyping.nominal_subtype('a' 'new' graph) return 2
    if subtyping.nominal_subtype('a' 'new' snapshot) return 3
    graph=snapshot
    if subtyping.nominal_subtype('a' 'new' graph) return 4
    graph=subtyping.Graph[]
    if subtyping.nominal_subtype('a' 'b' graph) return 5
    let unrelated=subtyping.from_links([subtyping.Link['a' 'elsewhere']])
    if subtyping.nominal_subtype('a' 'b' unrelated) return 6
    let fast=measure(true subtyping.default_links)
    let slow=measure(false subtyping.default_links)
    printl("{fast} {slow}")
    if fast <? 0 or slow <? 0 or fast*4 >=? slow return 7
    return 42
}
'''


def test_native_nominal_graph(tmp_path):
    source = tmp_path / 'nominal-graph.dewy'
    source.write_text(f'import p"{ROOT / "dewy/bootstrap/semantic/subtyping.dewy"}" as subtyping\n' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=30, check=False)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)
