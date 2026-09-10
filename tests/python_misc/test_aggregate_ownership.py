"""Owned union payloads are independent values and return their storage on exit."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def run(source, tmp_path):
    output = tmp_path / 'ownership.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.parametrize('payload', ['Bag', 'array<int64>', 'Node'])
@pytest.mark.parametrize('braced', [False, True])
def test_union_record_copy_reuses_memory_on_every_return(payload, braced, tmp_path):
    value = {'Bag': 'Bag[[loop i in 0..128 {i}]]',
             'array<int64>': '[loop i in 0..128 {i}]',
             'Node': 'Node[42 Node[7 none]]'}[payload]
    read = {'Bag': 'copy.payload.values.length', 'array<int64>': 'copy.payload.length',
            'Node': 'copy.payload.value'}[payload]
    yes, no = f'return {read}', 'return 0'
    if braced:
        yes, no = '{' + yes + '}', '{' + no + '}'
    source = '''
Bag:type=[values:array<int64>]
Node:type=[value:int64 next:Node|none]
''' + f'''
Box:type=[payload:{payload}|none]
let snapshot=(value:Box):>int64=>{{
    let copy=value
    if copy.payload is? none {no} else {yes}
}}
let main=():>int64=>{{
    let value=Box[{value}]
    snapshot(value);
    snapshot(value);
    loop i in 0..20 {{
        snapshot(value);
        snapshot(Box[none]);
        printl(_arena_cursor)
    }}
    return 0
}}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 21
    # Printing itself warms a function region on the first two iterations.
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('discard', ['clear', 'truncate(0)'])
def test_union_array_copy_releases_payloads_and_preserves_the_source(discard, tmp_path):
    source = '''
Bag:type=[values:array<int64>]
Other:type=[text:string]
let snapshot=(value:array<Bag|Other>):>int64=>{
    let copy=value
    copy.clear
    $runtime_assert value.length =? 2
    return value.length
}
let main=():>int64=>{
    let value:array<Bag|Other>=[Bag[[loop i in 0..128 {i}]] Other["ok"]]
    snapshot(value);
    snapshot(value);
    loop i in 0..20 {
        $runtime_assert snapshot(value) =? 2
        printl(_arena_cursor)
    }
    return 0
}
'''
    cursors = run(source.replace('copy.clear', 'copy.' + discard), tmp_path).splitlines()
    # Printing itself warms a function region on the first two iterations.
    assert len(set(cursors[2:])) == 1, cursors


def test_optional_string_array_copies_own_their_payload(tmp_path):
    source = '''
let main=():>int64=>{
    let value:array<string|none>=["longer-{42}" none]
    let copy:array<string|none>=value
    value.clear
    let overwrite:array<string|none>=["short-{17}" none]
    $runtime_assert copy.length =? 2
    let kept=copy[0]
    $runtime_assert kept is? string
    $runtime_assert kept =? "longer-42"
    return 0
}
'''
    run(source, tmp_path)
