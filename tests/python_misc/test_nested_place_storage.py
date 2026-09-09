"""Nested values stored through a place must survive the storing call's frame."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_nested_place_assignments_outlive_stack_reuse(tmp_path):
    scratch = ' '.join('123' for _ in range(512))
    source = f'''
Box:type = [mapping:dict<string int64> values:array<int64> fixed:array<int64 length=2>]
let fill = (@box:Box):>void => {{
    box.mapping = ['key' -> 7]
    let original:array<int64> = [9 10]
    box.values = original
    original[0] = 88
    box.fixed = [11 12]
}}
let overwrite_stack = ():>int64 => {{
    let scratch:array<int64 length=512> = [{scratch}]
    return scratch[511]
}}
let main = ():>int64 => {{
    let box = Box[[] [] [0 0]]
    fill(@box)
    overwrite_stack;
    if 'key' in? box.mapping printl(box.mapping['key'])
    else return 1
    if box.values.length =? 2 {{ printl(box.values[0]) printl(box.values[1]) }}
    else return 2
    printl(box.fixed[0])
    printl(box.fixed[1])
    return 0
}}
'''
    output = tmp_path / 'nested_place.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['7', '9', '10', '11', '12']


def test_whole_object_place_replacement_keeps_nested_storage(tmp_path):
    scratch = ' '.join('123' for _ in range(512))
    source = f'''
Source:type=const [text:string values:array<int64> fixed:array<int64 length=2>]
State:type=[sources:array<Source>=[] flags:set<string>=set[]]
Saved:type=const [state:State]
let replace_state=(@state:State):>void => {{
    let candidate=State[[Source["retained" [7 9] [11 13]]] set["ready"]]
    let winner:Saved?=none
    winner=Saved[candidate]
    $runtime_assert winner isnt? none
    state=winner.state
    candidate.sources.clear
    candidate.flags.clear
}}
let retain=(@state:State):>void => {{state=state}}
let overwrite_stack=():>int64 => {{
    let scratch:array<int64 length=512>=[{scratch}]
    return scratch[511]
}}
let main=():>int64 => {{
    let state=State[]
    loop i in 0..31 {{
        replace_state(@state)
        retain(@state)
        overwrite_stack;
    }}
    if state.sources.length not=? 1 return 1
    let source=state.sources[0]
    printl(source.text)
    if source.values.length not=? 2 return 2
    printl(source.values[0])
    printl(source.values[1])
    printl(source.fixed[0])
    printl(source.fixed[1])
    printl("ready" in? state.flags)
    return 0
}}
'''
    output = tmp_path / 'whole_place.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['retained', '7', '9', '11', '13', 'true']
