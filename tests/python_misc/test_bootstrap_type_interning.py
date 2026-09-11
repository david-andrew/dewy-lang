"""Interning hints must remain valid across independent and forked arenas."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_interning_checks_hints_against_the_current_arena(tmp_path):
    source = tmp_path / 'interning.dewy'
    source.write_text(
        f'import p"{ROOT / "dewy/bootstrap/semantic/ty.dewy"}" as types\n'
        + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], check=False,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr
    assert result.stdout == 'Independent, forked, and cleared type arenas passed\n'


BODY = '''let main=():>int64=>{
    let left:array<types.Type>=[]
    let right:array<types.Type>=[]
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
    right=[]
    if types.primitive('string' @right) not=? 0 return 10
    if left.length not=? 3 or fork.length not=? 4 or right.length not=? 1 return 11
    printl('Independent, forked, and cleared type arenas passed')
    return 42
}
'''
