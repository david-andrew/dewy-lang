"""Structural identity shares child graphs without merging stored metadata."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
BODY = '''
layer=(child:addr @nodes:types.Table):>addr=>types.object_type([types.ObjectField['a' child] types.ObjectField['b' child]] none false [] [] @nodes)
main=():>int64=>{
    let nodes=types.Table[]
    let word=types.primitive('int64' @nodes)
    let left=types.object_type([types.ObjectField['value' word default=17]] none false [] [] @nodes)
    let right=types.object_type([types.ObjectField['value' word default=23]] none false [] [] @nodes)
    let before:int64=_arena_allocated_bytes
    loop depth in 0..11 {
        left=layer(left @nodes)
        right=layer(right @nodes)
        if left =? right or not types.same_type(left right nodes) return 1
    }
    printl(_arena_allocated_bytes-before)
    let key=types.shape_of(left nodes)
    printl(key.length)
    if types.shapes_key([left] nodes) not=? types.shapes_key([right] nodes) return 2
    let distinct=types.object_type([types.ObjectField['a' left] types.ObjectField['c' left]] none false [] [] @nodes)
    if types.same_type(layer(left @nodes) distinct nodes) return 3
    let alias=types.named_type('First' 100 @nodes)
    let other=types.named_type('Second' 101 @nodes)
    types.resolve_alias(alias left @nodes)
    types.resolve_alias(other left @nodes)
    if types.same_type(alias other nodes) or types.same_type(alias word nodes) return 4
    let fork=nodes
    types.truncate(@nodes 0)
    let flag=types.primitive('bool' @nodes)
    let replacement=types.object_type([types.ObjectField['value' flag default=17]] none false [] [] @nodes)
    loop depth in 0..11 {replacement=layer(replacement @nodes)}
    # Reused stored ids must not reinterpret references in existing keys.
    if types.shape_of(replacement nodes) =? key return 5
    if types.shape_of(left fork) not=? key or not types.same_type(left right fork) return 6
    return 42
}
'''


def test_shared_structural_graphs_have_compact_exact_keys(tmp_path):
    source = tmp_path / 'structural-ids.dewy'
    source.write_text(f'import p"{ROOT / "dewy/bootstrap/semantic/ty.dewy"}" as types\n' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=30, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)
        allocated, key_length = map(int, run.stdout.splitlines())
        assert 0 <= allocated < 5_000_000
        assert key_length < 100
