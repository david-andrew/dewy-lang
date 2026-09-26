"""Type lookup indexes belong to their arena and follow forks and rollback."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_interning_keeps_the_index_with_its_arena(tmp_path):
    source = tmp_path / 'interning.dewy'
    source.write_text(
        f'import p"{ROOT / "dewy/bootstrap/semantic/ty.dewy"}" as types\n'
        + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], check=False,
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 42, result.stdout + result.stderr
        assert result.stdout == 'Independent, forked, and cleared type arenas passed\n'


BODY = '''let main=():>int64=>{
    let left:types.Table=types.Table[]
    let right:types.Table=types.Table[]
    if types.primitive('int64' @left) not=? 0 return 1
    if types.primitive('bool' @left) not=? 1 return 2
    if types.primitive('bool' @right) not=? 0 return 3
    if types.primitive('int64' @right) not=? 1 return 4
    if types.primitive('int64' @left) not=? 0 return 5
    let fork=left
    if types.primitive('string' @left) not=? 2 return 6
    if types.primitive('uint64' @fork) not=? 2 return 7
    if types.primitive('string' @fork) not=? 3 return 8
    if types.primitive('string' @left) not=? 2 return 9
    right=types.Table[]
    if types.primitive('string' @right) not=? 0 return 10
    if left.entries.length not=? 3 or fork.entries.length not=? 4 or right.entries.length not=? 1 return 11
    # Truncation must erase the discarded keys before ids are reused. A fork
    # retains both its old descriptions and its own index independently.
    let saved=fork
    types.truncate(@fork 2)
    if fork.positions.length not=? 2 return 12
    if types.primitive('float64' @fork) not=? 2 return 13
    if types.primitive('string' @fork) not=? 3 return 14
    if types.primitive('uint64' @saved) not=? 2 return 15
    if types.primitive('string' @saved) not=? 3 return 16
    if types.node_at(fork 2).key =? types.node_at(saved 2).key return 17
    types.truncate(@fork 0)
    if fork.positions.length not=? 0 or fork.entries.length not=? 0 return 18
    if types.primitive('bool' @fork) not=? 0 return 19
    let alias=types.named_type('Later' 7 @fork)
    types.resolve_alias(alias 0 @fork)
    if types.named_type('Later' 7 @fork) not=? alias return 20
    if types.unfold(alias fork) not=? 0 return 21
    if fork.positions.length not=? fork.entries.length return 22
    let literals=types.Table[]
    let texts:array<string>=['' 'x' '\"x\"' 'a:1,b' 'B00' 'é' 'é']
    let text_ids:set<addr>=set[]
    loop text in texts {
        let id=types.string_literal(text @literals)
        if types.string_literal(text @literals) not=? id return 23
        text_ids.push(id)
    }
    if text_ids.length not=? texts.length return 24
    let binaries:array<array<uint8>>=[[] [0] [0 0] [1 23] [12 3] [255] [10 11] [171]]
    let binary_ids:set<addr>=set[]
    loop i in 0.. and i <? binaries.length {
        let bytes=binaries[i]
        let id=types.binary_literal(bytes @literals)
        if types.binary_literal(bytes @literals) not=? id return 25
        if id in? text_ids return 26
        binary_ids.push(id)
    }
    if binary_ids.length not=? binaries.length return 27
    let original=literals
    types.truncate(@literals 0)
    let replacement=types.binary_literal([255] @literals)
    if replacement not=? 0 return 28
    if types.string_literal('x' @original) not in? text_ids return 29
    if types.binary_literal([255] @original) not in? binary_ids return 30
    printl('Independent, forked, and cleared type arenas passed')
    return 42
}
'''
