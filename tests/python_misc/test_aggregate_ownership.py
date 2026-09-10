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


def test_returned_record_owns_nested_dynamic_array_rows(tmp_path):
    source = '''
Rows:type=[values:array<array<int64>>]
let make=(count:int64):>Rows=>{
    let rows:array<array<int64>>=[]
    loop i in 0.. and i <? count {rows.push([20 22])}
    return Rows[rows]
}
let exercise=():>void=>{
    let rows=make(3)
    let copy=rows
    $runtime_assert rows.values.length >? 0 and copy.values.length >? 0
    copy.values[0]=[99]
    let original=rows.values[0]
    let changed=copy.values[0]
    $runtime_assert original.length =? 2 and changed.length =? 1
    $runtime_assert original[0]+original[1] =? 42
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


def test_returned_dictionary_owns_array_values(tmp_path):
    source = '''
Snapshot:type=[values:dict<int64 array<int64>>]
let make=():>Snapshot=>Snapshot[[1->[20 22] 2->[7]]]
let exercise=():>void=>{
    let snapshot=make()
    let copy=snapshot
    copy.values[1]=[99]
    let original=snapshot.values.get(1 [])
    $runtime_assert original.length =? 2
    $runtime_assert original[0]+original[1] =? 42
    copy.values.clear
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


def test_container_algebra_reads_left_before_effectful_right(tmp_path):
    source = '''
let left:set<int64>=set[40]
let change=():>set<int64>=>{left.clear left.add(99) return set[2]}
let exercise=():>void=>{
    left.clear left.add(40)
    let result=left|change()
    let total:int64=0
    loop value in result {total+=value}
    $runtime_assert total =? 42
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


def test_module_algebra_owns_string_members_and_values(tmp_path):
    source = '''
let suffix:int64=42
let left:set<string>=set["left-{suffix}" "shared-{suffix}"]
let right:set<string>=set["right-{suffix}" "shared-{suffix}"]
let united=(left|right)|set["last"]
let common=left&right
let distinct=left-right
let first:dict<string string>=["key-{suffix}"->"old-{suffix}"]
let second:dict<string string>=["key-{suffix}"->"new-{suffix}"]
let merged=first|second
left.clear right.clear first.clear second.clear
let exercise=():>void=>{
    let copy=united|set["extra"]
    $runtime_assert "left-42" in? copy and "right-42" in? copy
    $runtime_assert "shared-42" in? common and "left-42" in? distinct
    $runtime_assert merged.get("key-42" "missing") =? "new-42"
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


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


@pytest.mark.parametrize('source', ['table.get(1)', 'values[0]', 'selected_value()'])
def test_string_retained_from_a_narrowed_cell_outlives_its_scope(source, tmp_path):
    program = '''
let selected_value=():>string|none=>"retained payload"
let inspect=(present:bool):>int64=>{
    let name:string="fallback"
    if present {
        let table:dict<int64 string>=[1 -> "retained payload"]
        let values:array<string|none>=["retained payload"]
        let selected=SOURCE
        if selected is? none return 0
        name=selected
    }
    # The payload's owner has left scope before this read.
    if present return if name =? "retained payload" 42 else 1
    return if name =? "fallback" 42 else 1
}
let main=():>int64=>{
    inspect(true);
    inspect(false);
    loop i in 0..20 {
        $runtime_assert inspect(true) =? 42
        $runtime_assert inspect(false) =? 42
        printl(_arena_cursor)
    }
    return 0
}
'''.replace('SOURCE', source)
    cursors = run(program, tmp_path).splitlines()
    assert len(cursors) == 21
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('element,value', [
    ('int64|none', '42'),
    ('Item|Other', 'Item["retained payload"]'),
])
def test_fixed_array_cell_elements_release_after_parameter_copy(element, value, tmp_path):
    source = """
Item:type=[text:string]
Other:type=[value:int64]
let inspect=(source:array<ELEMENT length=1>):>int64=>{
    let copy=source
    return copy.length
}
let main=():>int64=>{
    loop i in 0..20 {
        let source:array<ELEMENT length=1>=[VALUE]
        $runtime_assert inspect(source) =? 1
        printl(_arena_cursor)
    }
    return 0
}
""".replace('ELEMENT', element).replace('VALUE', value)
    cursors = run(source, tmp_path).splitlines()
    assert len(set(cursors[2:])) == 1, cursors


def test_record_field_takes_ownership_of_fresh_call_result(tmp_path):
    source = '''
Box:type=[words:array<string>]
Outer:type=[box:Box]
let calls:int64=0
let make=():>Box=>{calls+=1 return Box[["value-{calls}"]]}
let exercise=():>void=>{
    let value=Outer[make()]
    $runtime_assert value.box.words.length=?1
    let kept=value.box.words[0]
    value.box.words.clear
    $runtime_assert kept=?"value-{calls}"
}
let main=():>int64=>{
    loop warmup in 0..12 {exercise();}
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('replacement', ['Box[value.words]', 'copy(value)'])
def test_fresh_record_replacements_transfer_fields_before_releasing_old_value(replacement, tmp_path):
    source = '''
Box:type=[words:array<string>]
Outer:type=[box:Box]
let copy=(value:Box):>Box=>value
let replace=(@value:Box):>void=>{value=REPLACEMENT}
let exercise=():>void=>{
    let value=Box[["owned words"]]
    let kept=value.words
    value=REPLACEMENT
    replace(@value)
    let outer=Outer[value]
    outer.box=FIELD_REPLACEMENT
    outer.box.words.clear
    value.words.clear
    $runtime_assert kept.length=?1
    $runtime_assert kept[0]=?"owned words"
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''.replace('FIELD_REPLACEMENT', replacement.replace('value', 'outer.box')).replace('REPLACEMENT', replacement)
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('result_type', ['Box', 'Box|none', 'Box|string', 'array<string>|none'])
def test_discarded_call_statements_release_their_payloads(result_type, tmp_path):
    value = 'words' if result_type.startswith('array') else 'Box[words]'
    alternative = ('if calls % 2 =? 0 return none' if '|none' in result_type
                   else 'if calls % 2 =? 0 return "other-{calls}"' if '|string' in result_type
                   else '')
    source = f'''
Box:type=[words:array<string>]
let calls:int64=0
let make=():>{result_type}=>{{
    calls+=1
    {alternative}
    let words:array<string>=["value-{{calls}}"]
    return {value}
}}
let exercise=():>void=>{{
    let before=calls
    make(); make();
    $runtime_assert calls=?before+2
}}
let main=():>int64=>{{
    loop warmup in 0..12 {{exercise();}}
    loop i in 0..12 {{exercise(); printl(_arena_cursor)}}
    return 0
}}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('value_type', ['Box', 'Box|none', 'Box|string'])
def test_fresh_arguments_and_parameter_copies_release_after_retaining_results(value_type, tmp_path):
    source = '''
Box:type=[words:array<string>]
let calls:int64=100
let make=():>VALUE_TYPE=>{calls+=1 return Box[["payload-{calls}"]]}
let take=(value:VALUE_TYPE):>string=>{
    if value isnt? Box return "other"
    $runtime_assert value.words.length=?1
    let result=value.words[0]
    value.words.clear
    return result
}
let defaulted=(value:VALUE_TYPE=make()):>string=>take(value)
let exercise=():>void=>{
    let original=make()
    let kept=take(original)
    $runtime_assert original is? Box
    $runtime_assert original.words.length=?1
    let positional=take(make())
    let keyword=take(value=make())
    let packed=take(Box[["literal"]])
    let omitted=defaulted()
    $runtime_assert kept.startswith("payload-")
    $runtime_assert positional.startswith("payload-")
    $runtime_assert keyword.startswith("payload-")
    $runtime_assert omitted.startswith("payload-")
    $runtime_assert packed=?"literal"
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''.replace('VALUE_TYPE', value_type)
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


def test_optional_argument_decoding_retains_conversion_and_owned_result(tmp_path):
    source = '''
let keep=(value:string|none):>string=>if value is? none "absent" else value
let exercise=():>void=>{
    let good:array<uint8>=[65]
    let invalid:array<uint8>=[255]
    let retained=keep(good as string|none)
    $runtime_assert keep(invalid as string|none)=?"absent"
    $runtime_assert retained=?"A"
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('result_type', ['Box|none', 'Box|string', 'array<string>|none'])
def test_discarded_call_type_tests_release_their_payloads(result_type, tmp_path):
    value = 'words' if result_type.startswith('array') else 'Box[words]'
    tested = 'array<string>' if result_type.startswith('array') else 'Box'
    source = f'''
Box:type=[words:array<string>]
let calls:int64=0
let make=():>{result_type}=>{{
    calls+=1
    let words:array<string>=["value-{{calls}}"]
    return {value}
}}
let exercise=():>void=>{{
    let before=calls
    $runtime_assert make() is? {tested}
    $runtime_assert not (make() isnt? {tested})
    $runtime_assert calls=?before+2
}}
let main=():>int64=>{{
    exercise(); exercise();
    loop i in 0..12 {{exercise(); printl(_arena_cursor)}}
    return 0
}}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


def test_discarded_base_record_type_test_releases_dynamic_child_fields(tmp_path):
    source = '''
Node:type=type of [key:string shape:string|none]
Child:type=type of Node & [parts:array<array<string>>]
Other:type=type of Node & [value:int64]
let calls:int64=0
let read=(nodes:array<Node>):>Node=>{
    calls+=1
    if nodes.length >? 0 {return nodes[0]}
    return Node["" none]
}
let exercise=(nodes:array<Node>):>void=>{
    let before=calls
    $runtime_assert read(nodes) is? Child
    $runtime_assert read(nodes) isnt? Other
    $runtime_assert read(nodes) is? Child|Other
    $runtime_assert calls=?before+3
}
let main=():>int64=>{
    let nodes:array<Node>=[Child["key" "shape" [["payload"]]]]
    exercise(nodes); exercise(nodes);
    loop i in 0..12 {exercise(nodes); printl(_arena_cursor)}
    let original=read(nodes)
    $runtime_assert original is? Child and original.key=?"key" and original.shape=?"shape"
    let parts=original.parts
    $runtime_assert parts.length >? 0
    let words=parts[0]
    $runtime_assert words.length >? 0
    $runtime_assert words[0]=?"payload"
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('interpolated', [False, True])
def test_returned_record_field_views_release_receivers_after_retaining_values(interpolated, tmp_path):
    source = '''
Node:type=type of [key:string shape:string|none]
Child:type=type of Node & [parts:array<array<string>>]
let calls:int64=0
let make=():>Child=>{
    calls+=1
    return Child["key" "shape" [["payload"]]]
}
let read=():>Node=>make()
let key=():>string=>read().key
let parts=():>array<array<string>>=>make().parts
let exercise=():>void=>{
    let before=calls
    let retained=read().key
    let shape=read().shape
    let returned=key()
    let rows=parts()
    let skipped=false and read().key.length >? 0
    $runtime_assert not skipped and calls=?before+4
    # Further allocations must not overwrite any of the retained fields.
    $runtime_assert read().key.length >? 0
    $runtime_assert retained=?"key"
    $runtime_assert shape=?"shape"
    $runtime_assert returned=?"key"
    $runtime_assert rows.length >? 0
    let words=rows[0]
    $runtime_assert words.length >? 0
    $runtime_assert words[0]=?"payload"
    loop read().key.length >? 0 and calls <? before+8 {}
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''
    if interpolated:
        source = source.replace('Child["key" "shape" [["payload"]]]',
                                'Child["key-{calls}" "shape-{calls}" [["payload-{calls}"]]]')
        source = source.replace('retained=?"key"', 'retained=?"key-{before+1}"')
        source = source.replace('shape=?"shape"', 'shape=?"shape-{before+2}"')
        source = source.replace('returned=?"key"', 'returned=?"key-{before+3}"')
        source = source.replace('words[0]=?"payload"', 'words[0]=?"payload-{before+4}"')
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


@pytest.mark.parametrize('array', [False, True])
def test_optional_call_binding_takes_ownership_without_abandoning_payload(array, tmp_path):
    result_type = 'array<string>' if array else 'Box'
    value = 'words' if array else 'Box[words]'
    read = 'own' if array else 'own.words'
    original = 'maybe' if array else 'maybe.words'
    source = f'''
Box:type=[words:array<string>]
let make=():>{result_type}|none=>{{
    let number:int64=42
    let words:array<string>=["value-{{number}}"]
    return {value}
}}
let exercise=():>void=>{{
    let maybe=make()
    $runtime_assert maybe is? {result_type}
    let own=maybe
    $runtime_assert {read}.length =? 1
    {read}[0]="changed"
    let words={original}
    $runtime_assert words.length =? 1
    $runtime_assert words[0]=?"value-42"
}}
let main=():>int64=>{{
    exercise(); exercise();
    loop i in 0..12 {{exercise(); printl(_arena_cursor)}}
    return 0
}}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors


def test_record_call_snapshots_and_fresh_arguments_release_after_the_call(tmp_path):
    source = '''
State:type=[rows:array<array<string>>]
let make=():>State=>State[[["payload"]]]
let inspect=(value:State @shared:State):>int64=>{
    shared.rows.clear
    return value.rows.length+41
}
let read=(value:State):>int64=>value.rows.length+41
let text=(value:State):>string=>{
    let rows=value.rows
    $runtime_assert rows.length >? 0
    let words=rows[0]
    $runtime_assert words.length >? 0
    return words[0]
}
let exercise=():>void=>{
    let value=make()
    $runtime_assert inspect(value @value)=?42
    $runtime_assert value.rows.length=?0
    $runtime_assert read(make())=?42
    $runtime_assert read(State[[["literal"]]])=?42
    let retained=text(make())
    $runtime_assert read(make())=?42
    $runtime_assert retained=?"payload"
}
let main=():>int64=>{
    exercise(); exercise();
    loop i in 0..12 {exercise(); printl(_arena_cursor)}
    return 0
}
'''
    cursors = run(source, tmp_path).splitlines()
    assert len(cursors) == 13
    assert len(set(cursors[2:])) == 1, cursors
