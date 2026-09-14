"""Native normal forms are scoped to the arena and expire before id reuse."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]

BODY = '''
measure=(cached:bool id:addr @nodes:types.Table):>int64=>{
    let before:int64=_arena_allocated_bytes
    loop i in 0.. and i <? 128 {
        let result=if cached types.to_nnf(id @nodes) else types.to_nnf_uncached(id @nodes)
        if result not=? id return -1
    }
    return _arena_allocated_bytes-before
}
main=():>int64=>{
    let nodes=types.Table[]
    let word=types.primitive('int64' @nodes)
    # Explicit descriptions retain a non-normal child until normalization.
    let negated=types.intern(@nodes types.TypeNot[key='raw-not' item=word])
    let double=types.intern(@nodes types.TypeNot[key='raw-double-not' item=negated])
    let original=types.intern(@nodes types.ArrayType[key='raw-array' element=double])
    let checkpoint=nodes.entries.length
    let normalized=types.to_nnf(original @nodes)
    if normalized <? checkpoint return 1
    let array=types.node_at(nodes normalized)
    if array isnt? types.ArrayType or array.element not=? word return 2
    let fork=nodes
    types.truncate(@nodes checkpoint)
    let replacement=types.primitive('bool' @nodes)
    if replacement not=? normalized return 3
    let restored=types.to_nnf(original @nodes)
    if restored =? replacement return 4
    let again=types.node_at(nodes restored)
    if again isnt? types.ArrayType or again.element not=? word return 5
    if types.to_nnf(original @fork) not=? normalized return 6
    let alias=types.named_type('Later' 7 @nodes)
    if types.to_nnf(alias @nodes) not=? alias return 7
    types.resolve_alias(alias replacement @nodes)
    if types.unfold(types.to_nnf(alias @nodes) nodes) not=? replacement return 8
    # Repeated normal queries must not reconstruct an unchanged record's
    # fields. Compare with the real uncached walk as a positive cost control.
    let fields:array<types.ObjectField>=[]
    loop i in 0.. and i <? 32 {fields.push(types.ObjectField["field{i}" word])}
    let record=types.object_type(fields none false [] [] @nodes)
    if types.to_nnf(record @nodes) not=? record return 9
    let fast=measure(true record @nodes)
    let slow=measure(false record @nodes)
    printl("{fast} {slow}")
    if fast <? 0 or slow <? 0 or fast*4 >=? slow return 10
    return 42
}
'''


def test_native_normalization_cache_preserves_arena_identity(tmp_path):
    source = tmp_path / 'normalization.dewy'
    source.write_text(f'import p"{ROOT / "dewy/bootstrap/semantic/ty.dewy"}" as types\n' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=30, check=False)
        assert result.returncode == 42, result.stdout + result.stderr
