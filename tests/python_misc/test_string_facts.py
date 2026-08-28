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
    with pytest.raises(UserError, match='string index is not proven'):
        _compile('let main = ():>int64 => { let word:string = "abc"  let text:string = "longer"  word = text  let c:string = word[2]  return 0 }\n')
    _compile('let main = ():>int64 => { let word:string = "abc"  word = "de"  let c:string = word[1]  return 0 }\n')


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
