"""Array element reads must survive replacement of their original slot."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('capture', [
    'values[1]',
    'alias',
    'values[1][..]',
    '{values[1]}',
    'if argv.length >? 0 values[1] else "unused"',
])
def test_retained_string_elements_survive_a_swap(tmp_path, capture):
    source = '''let make=(text:string):>string=>"prefix:{text}"
let main=(argv:array<string>):>int64=>{
    let values:array<string>=[]
    values.push(make("first"))
    values.push(make("second"))
    let alias=values[1]
    let second=CAPTURE
    let first=values[0]
    values[1]=first
    values[0]=second
    let scratch=make("overwritten")
    printl(values[0])
    printl(values[1])
    printl(first)
    printl(second)
    printl(scratch)
    return 0
}
'''
    source = source.replace('CAPTURE', capture)
    output = tmp_path / 'retained_string.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'prefix:second\nprefix:first\nprefix:first\nprefix:second\nprefix:overwritten\n'


def test_retained_string_field_survives_replacement(tmp_path):
    source = '''Box:type=[text:string]
let make=(text:string):>string=>"prefix:{text}"
let main=():>int64=>{
    let box=Box[make("kept")]
    let saved=box.text
    box.text=make("new")
    let scratch=make("overwritten")
    printl(saved)
    printl(box.text)
    printl(scratch)
    return 0
}
'''
    output = tmp_path / 'retained_field.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'prefix:kept\nprefix:new\nprefix:overwritten\n'
