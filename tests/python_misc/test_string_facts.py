"""Runtime-length strings are indexed and sliced from length facts, like arrays."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def test_guards_prove_string_indexes_and_slices() -> None:
    _compile(
        'let f = (text:string i:int64 a:int64 b:int64):>string => {\n'
        '    if i >=? 0 and i <? text.length { return text[i] }\n'
        '    if a >=? 0 and a <? text.length and b <? text.length and a <=? b { return text[a..b] }\n'
        '    if text.length >? 0 { return text[text.length - 1] }\n'
        '    return ""\n'
        '}\n'
    )


def test_literal_initializers_and_reassignment_track_the_length() -> None:
    _compile('let main = ():>int64 => { let word:string = "abc"  let c:string = word[2]  let ab:string = word[0..1]  return 0 }\n')
    _compile('let main = ():>int64 => { let word:string = "abc"  let text:string = "longer"  word = text  let c:string = word[2]  return 0 }\n')
    with pytest.raises(UserError, match='string index is not proven'):
        _compile('let f = (text:string):>string => { let word:string = "abc"  word = text  return word[2] }\n')
    _compile('let main = ():>int64 => { let word:string = "abc"  word = "de"  let c:string = word[1]  return 0 }\n')


@pytest.mark.parametrize('binding', ['let word:string = ctx.ending.text', 'let word:string = ""\nword = ctx.ending.text'])
def test_member_length_facts_transfer_on_declaration_and_assignment(binding: str) -> None:
    _compile(
        'End:type = const [text:string<length >? 0>]\n'
        'Context:type = const [ending:End]\n'
        f'let first = (ctx:Context):>string => {{ {binding}\nreturn word[0] }}\n'
    )


def test_sequence_length_transfer_snapshots_the_incoming_value() -> None:
    _compile('let f = (source:string):>string => {\n'
             '    if source.length <? 3 return ""\n'
             '    let word:string = source\n'
             '    source = ""\n'
             '    word = word[1..]\n'
             '    return word[1]\n}\n')
    with pytest.raises(UserError, match='string index is not proven'):
        _compile('let f = (source:string):>string => {\n'
                 '    if source.length <? 3 return ""\n'
                 '    let word:string = source\n'
                 '    word = ""\n'
                 '    return word[0]\n}\n')


@pytest.mark.parametrize('binding', ['let copy:array<int64> = source', 'let copy:array<int64> = []\ncopy = source'])
def test_array_length_transfer_is_a_value_snapshot(binding: str) -> None:
    _compile('let f = (source:array<int64>):>int64 => {\n'
             '    if source.length <? 2 return 0\n'
             f'    {binding}\n'
             '    source.clear\n'
             '    return copy[1]\n}\n')


def test_unproven_string_indexes_and_slices_are_rejected() -> None:
    with pytest.raises(UserError, match='string index is not proven'):
        _compile('let f = (text:string i:int64):>string => text[i]\n')
    with pytest.raises(UserError, match='not proven'):
        _compile('let f = (text:string i:int64):>string => { if i >=? 0 { return text[i] }  return "" }\n')
    with pytest.raises(UserError, match='slice'):
        _compile('let f = (text:string a:int64 b:int64):>string => { if a >=? 0 and a <? text.length { return text[a..b] }  return "" }\n')


def test_end_desugars_to_length_minus_one_on_runtime_sequences() -> None:
    _compile(
        'let f = (text:string xs:array<int64>):>int64 => {\n'
        '    let total:int64 = 0\n'
        '    if text.length >? 1 { let last:string = text[end]  let pair:string = text[end - 1..end]  total += pair.length }\n'
        '    if xs.length >? 2 { total += xs[end] + xs[end - 2] }\n'
        '    if text.length >? 3 { total += text[1..end - 1].length }\n'
        '    return total\n'
        '}\n'
    )
    with pytest.raises(UserError, match='string index is not proven'):
        _compile('let f = (text:string):>string => text[end]\n')  # the string may be empty
    with pytest.raises(UserError, match='not proven'):
        _compile('let f = (text:string):>string => { if text.length >? 0 { return text[end - 1] }  return "" }\n')


@pytest.mark.parametrize('second', ['string<length >? 0>', 'string'])
def test_common_union_field_length_facts(second: str) -> None:
    source = (
        'A = type of any & const [text:string<length >? 0>]\n'
        f'B = type of any & const [text:{second}]\n'
        'let first = (ending:A|B):>string => { let text = ending.text\nreturn text[0] }\n'
    )
    if second == 'string':
        with pytest.raises(UserError, match='string index is not proven'):
            _compile(source)
    else:
        _compile(source)


@pytest.mark.parametrize('condition', ['i+1 <? stop', 'stop >? i+1'])
def test_offset_comparisons_prove_the_next_index(condition):
    _compile(f'''f = (xs:array<int64> i:addr stop:addr):>int64 => {{
        if stop >? xs.length return 0
        if {condition} return xs[i+1]
        return 0
    }}''')


def test_non_strict_offset_comparison_does_not_prove_an_index():
    with pytest.raises(UserError, match='index is not proven'):
        _compile('''f = (xs:array<int64> i:addr stop:addr):>int64 => {
            if stop >? xs.length return 0
            if i+1 <=? stop return xs[i+1]
            return 0
        }''')


def test_optional_field_retains_the_narrowed_payload_contract():
    _compile('''Position:type = [value:addr?]
    f = (position:Position):>addr => {
        if position.value is? none return 0
        return position.value
    }''')
