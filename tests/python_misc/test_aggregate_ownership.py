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


@pytest.mark.parametrize('value_type,first,second,read', [
    ('string', '"first-{42}"', '"second-{17}"', 'value =? "second-17"'),
    ('Offset', 'Offset[Term[1 "first-{42}"] 0]', 'Offset[Term[2 "second-{17}"] 0]', 'value.term.projection =? "second-17"'),
    ('Offset|none', 'none', 'Offset[Term[2 "second-{17}"] 0]', 'value isnt? none and value.term.projection =? "second-17"'),
])
def test_dictionary_compaction_moves_live_elements_and_releases_dead_ones(value_type, first, second, read, tmp_path):
    source = f'''
Term:type=const [binding:int64 projection:string]
Offset:type=const [term:Term shift:int64]
let exercise=():>void=>{{
    let entries:dict<string {value_type}>=["a-{{1}}" -> {first} "b-{{2}}" -> {second} "c-{{3}}" -> {first}]
    if 'a-1' in? entries {{entries.pop('a-1');}}
    let copy=entries
    # Iteration compacts a dead first entry, moving both later entries.
    $runtime_assert entries.values.length =? 2
    entries.clear
    # The independent copy still owns both its live values and its tombstone
    # until its own compaction. Reusing freed blocks must not change either.
    let overwrite:array<string>=["reuse-{{99}}" "reuse-{{100}}"]
    $runtime_assert copy.values.length =? 2
    $runtime_assert 'b-2' in? copy
    let value=copy['b-2']
    $runtime_assert {read}
    if 'c-3' in? copy {{copy.pop('c-3');}}
    $runtime_assert copy.values.length =? 1
}}
let main=():>int64=>{{
    exercise()
    exercise()
    loop i in 0..20 {{exercise() printl(_arena_cursor)}}
    return 0
}}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 21
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('optional', [False, True])
def test_local_union_payload_copies_and_replacements_reuse_storage(optional, tmp_path):
    source = '''
Bag:type=[values:array<int64>]
Other:type=[text:string]
Payload:type=Bag|Other
let snapshot=(value:array<Payload>):>int64=>{
    $runtime_assert value.length >? 0
    let first:Payload=value[0]
    first=first
    let copy:Payload=first
    first=Other["empty"]
    first=copy
    if first is? Bag return first.values.length
    return 0
}
let main=():>int64=>{
    let value:array<Payload>=[Bag[[loop i in 0..128 {i}]]]
    loop i in 0..20 {
        $runtime_assert snapshot(value) =? 129
        printl(_arena_cursor)
    }
    return 0
}
'''
    if optional:
        source = source.replace('Payload:type=Bag|Other', 'Payload:type=Bag|none').replace('first=Other["empty"]', 'first=none')
    cursors = run(source, tmp_path).splitlines()
    assert len(set(cursors[2:])) == 1, cursors


def test_returning_a_local_union_keeps_its_payload_alive(tmp_path):
    source = '''
Bag:type=[values:array<int64>]
Payload:type=Bag|string|none
let make=(number:int64):>Payload=>{
    let result:Payload=Bag[[number number+1]]
    if number <? 0 {result="value-{number}"}
    return result
}
let inspect=(number:int64):>int64=>{
    let result=make(number)
    if result is? Bag return result.values.length
    if result is? string return result.length
    return 0
}
let main=():>int64=>{
    loop i in 0..20 {
        $runtime_assert inspect(42) =? 2
        $runtime_assert inspect(-1) =? 8
        printl(_arena_cursor)
    }
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(set(cursors[2:])) == 1, cursors


def test_returned_match_payload_survives_reuse_of_its_cell_storage(tmp_path):
    source = '''
let decode=(bytes:array<uint8>):>string=>{
    match bytes as string|none {text:string => return text <none> => return ""}
}
let main=():>int64=>{
    let kept=decode([65 66 67])
    loop i in 0..20 {
        let overwrite=decode([88 89 90])
        $runtime_assert overwrite =? "XYZ"
        $runtime_assert kept =? "ABC"
        $runtime_assert chr(65) =? "A"
    }
    return 0
}
'''
    run(source, tmp_path)


def test_checkpoint_field_replacements_release_previous_values(tmp_path):
    source = '''
Bag:type=[values:array<int64>]
Box:type=[nested:Bag values:array<int64> maybe:Bag|none text:string]
let restore=(@target:Box source:Box):>void=>{
    target.nested=source.nested
    target.values=source.values
    target.maybe=source.maybe
    target.text=source.text
    target.nested=target.nested
    target.values=target.values
    target.maybe=target.maybe
    target.text=target.text
}
let main=():>int64=>{
    let bag=Bag[[loop i in 0..128 {i}]]
    let source=Box[bag bag.values bag "snapshot-{42}"]
    let target=source
    loop i in 0..20 {
        restore(@target source)
        $runtime_assert target.values.length =? 129
        $runtime_assert target.nested.values.length =? 129
        $runtime_assert target.text =? "snapshot-42"
        printl(_arena_cursor)
    }
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(set(cursors[2:])) == 1, cursors


def test_array_call_result_transfers_elements_before_temporary_cleanup(tmp_path):
    source = '''
Param:type=const [name:string? value:addr required:bool=true place:bool=false]
Shape:type=[args:array<Param>]
let parameters=(shape:Shape):>array<Param>=>{let result=shape.args return result}
let main=():>int64=>{
    let shape=Shape[[Param["x" 0]]]
    loop i in 0..20 {
        shape.args=parameters(shape)
        $runtime_assert shape.args.length =? 1
        let first=shape.args[0]
        $runtime_assert first.name isnt? none
        $runtime_assert first.name =? "x"
        printl(_arena_cursor)
    }
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(set(cursors[2:])) == 1, cursors
