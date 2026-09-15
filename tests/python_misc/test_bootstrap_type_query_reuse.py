"""Repeated type queries preserve contracts, table forks, and truncated ids."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
SIGNATURE = 'signature=(args:array<addr> ret:addr @nodes:types.Table):>addr=>types.positional_function(args ret @nodes)'
BASELINE_SIGNATURE = '''signature=(args:array<addr> ret:addr @nodes:types.Table):>addr=>{
    let slots:array<types.PosOrKwArg>=[]
    loop argument in args {slots.push(types.PosOrKwArg[none argument])}
    return types.function_type(slots [] none ret [] @nodes)
}'''
BODY = '''
main=():>int64=>{
    let nodes=types.Table[]
    let word=types.primitive('int64' @nodes)
    let deep=word
    loop i in 0..23 {deep=types.array_type(deep none @nodes)}
    let record=types.object_type([types.ObjectField['value' deep]] none false [] [] @nodes)
    let args:array<addr>=[word word]
    let fn=signature(args word @nodes)
    let named=types.function_type([types.PosOrKwArg['a' word] types.PosOrKwArg[none word]] [] none word [] @nodes)
    let place=types.function_type([types.PosOrKwArg[none word place=true] types.PosOrKwArg[none word]] [] none word [] @nodes)
    if fn =? named or fn =? place return 1
    let merged=types.union([record word] @nodes)
    let both=types.intersect([record word] @nodes)
    let links=subtyping.Graph[]
    let count=nodes.entries.length
    let before:int64=_arena_allocated_bytes
    loop repeat in 0..499 {
        if signature(args word @nodes) not=? fn return 2
        if types.union([record word] @nodes) not=? merged return 3
        if types.intersect([record word] @nodes) not=? both return 4
        if not subtyping.covered(record record set[] links @nodes) return 5
    }
    printl(_arena_allocated_bytes-before)
    if nodes.entries.length not=? count return 6
    let later_fn=signature([fn deep] word @nodes)
    let later_union=types.union([fn deep] @nodes)
    let saved=nodes
    types.truncate(@nodes count)
    let reused=types.primitive('bool' @nodes)
    if reused not=? count return 7
    let rebuilt_fn=signature([fn deep] word @nodes)
    let rebuilt_union=types.union([fn deep] @nodes)
    if types.node_at(nodes rebuilt_fn) isnt? types.FunctionType return 8
    if types.node_at(nodes rebuilt_union) isnt? types.TypeOr return 9
    if types.node_at(saved later_fn) isnt? types.FunctionType or types.node_at(saved later_union) isnt? types.TypeOr return 10
    let independent=types.Table[]
    let flag=types.primitive('bool' @independent)
    let separate=signature([flag flag] flag @independent)
    let separate_node=types.node_at(independent separate)
    if separate_node isnt? types.FunctionType or separate_node.ret not=? flag return 11
    return 42
}
'''


def test_type_query_reuse_and_invalidation(tmp_path):
    source = tmp_path / 'query-reuse.dewy'
    source.write_text(f'import p"{ROOT / "dewy/bootstrap/semantic/ty.dewy"}" as types\n'
                      f'import p"{ROOT / "dewy/bootstrap/semantic/subtyping.dewy"}" as subtyping\n'
                      + SIGNATURE + '\n' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=30, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)
        assert 0 <= int(run.stdout.strip()) < 5_000_000
