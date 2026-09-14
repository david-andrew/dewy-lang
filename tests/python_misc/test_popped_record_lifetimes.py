"""Removed record elements must cross the array/result ownership boundary."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


ROOT = Path(__file__).resolve().parents[2]
NESTED = '''
Record:type=[items:array<int64>]
let take=(@values:array<Record>):>Record=>{
    if values.length >?0 return values.pop
    return Record[[]]
}
let exercise=():>bool=>{
    loop i in 0.. and i <?1000 {
        let values:array<Record>=[Record[[42]] Record[[7]]]
        let saved=values
        values.pop;
        let result=take(@values)
        if result.items.length not=?1 return false
        result.items[0]=99
        if saved.length not=?2 return false
        let first=saved[0]
        if first.items.length not=?1 or first.items[0] not=?42 return false
        values.push(result)
        let field=(values.pop).items
        if field.length not=?1 or field[0] not=?99 return false
    }
    return true
}
let live=():>int64=>_arena_live_bytes
let main=():>int64=>{
    if not exercise() return 2
    let before=live()
    if not exercise() return 3
    return if live()-before <=?4096 42 else 1
}
'''


@pytest.mark.parametrize('target', ['x86_64', 'c'])
@pytest.mark.parametrize('body', [
    (ROOT / 'tests/fixtures/native_read_temporaries.dewy').read_text(),
    NESTED,
    NESTED.replace('values.pop;', 'values.pop(1);'),
], ids=['scalar-records', 'nested-records', 'indexed-records'])
def test_popped_records_release_roots_and_preserve_retained_fields(tmp_path, target, body):
    source = tmp_path / 'popped-records.dewy'
    source.write_text(body)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr
