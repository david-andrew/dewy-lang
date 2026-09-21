"""Dependent length contracts keep the identity of their complete field route."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError
from tests.python_misc.test_scalar_projection import execute


PREFIX = '''
Inner:type=[entries:array<int64>]
Table:type=[inner:Inner unrelated:array<int64>]
last=(table:Table):>addr<i=>i <? table.inner.entries.length>=>{
    $runtime_assert table.inner.entries.length >? 0
    return table.inner.entries.length-1
}
read=(table:Table i:addr<i=>i <? table.inner.entries.length>):>int64=>table.inner.entries[i]
'''


APPEND = '''
Table:type=[entries:array<int64> positions:dict<int64 addr>]
intern=(@table:Table value:int64):>addr<i=>i <? table.entries.length>=>{
    let known=table.positions.get(value)
    if known isnt? none {
        $runtime_assert known <? table.entries.length
        return known
    }
    let id=table.entries.length
    table.entries.push(value)
    table.positions[value]=id
    return id
}
main=():>int64=>{
    let table=Table[[] []]
    let id=intern(@table 42)
    return table.entries[id]
}
'''

def positive_source():
    return PREFIX + '''
Reader:type=(table:Table):>addr<i=>i <? table.inner.entries.length>
reader:Reader=(table:Table):>addr=>{
    $runtime_assert table.inner.entries.length >? 0
    return table.inner.entries.length-1
}
main=():>int64=>{
    let table=Table[Inner[[20 42]] [1]]
    let index=last(table)
    if read(table index) not=? 42 return 1
    if table.inner.entries[reader(table)] not=? 42 return 2
    $runtime_assert table.inner.entries.length >? 0
    let local:addr<i=>i <? table.inner.entries.length>=0
    table.unrelated=[]
    if table.inner.entries[local] not=? 20 return 3
    return read(i=index table=table)
}
'''


def test_nested_result_parameter_and_local_terms(tmp_path):
    execute(tmp_path, 'nested-lengths', codegen(SrcFile(None, positive_source()), debug_locations=False))


@pytest.mark.parametrize('change', [
    'table.inner.entries=[]',
    'table.inner=Inner[[]]',
    'table=Table[Inner[[]] []]',
])
def test_mutating_the_route_invalidates_a_returned_index(change):
    source = PREFIX + f'''
main=():>int64=>{{
    let table=Table[Inner[[42]] []]
    let index=last(table)
    {change}
    return table.inner.entries[index]
}}
'''
    with pytest.raises(UserError):
        check.typecheck_and_resolve(SrcFile(None, source))


def test_nested_term_cannot_prove_a_different_root():
    source = PREFIX + '''
main=():>int64=>{
    let first=Table[Inner[[42]] []]
    let second=Table[Inner[[]] []]
    let index=last(first)
    return read(second index)
}
'''
    with pytest.raises(UserError):
        check.typecheck_and_resolve(SrcFile(None, source))


def test_unknown_field_in_a_result_contract_is_rejected():
    with pytest.raises(UserError, match='unknown field route'):
        check.typecheck_and_resolve(SrcFile(None, '''
Table:type=[entries:array<int64>]
wrong=(table:Table):>addr<i=>i <? table.missing.length>=>0
'''))


def test_later_argument_mutation_does_not_rebind_a_snapshot_contract():
    with pytest.raises(UserError):
        check.typecheck_and_resolve(SrcFile(None, PREFIX + '''
first=(table:Table ignored:int64):>addr<i=>i <? table.inner.entries.length>=>{
    $runtime_assert table.inner.entries.length >? 0
    return 0
}
clear=(@table:Table):>int64=>{table.inner.entries=[] return 0}
main=():>int64=>{
    let table=Table[Inner[[42]] []]
    let index=first(table clear(@table))
    return table.inner.entries[index]
}
'''))


def test_parameter_bound_cannot_use_a_later_larger_array():
    with pytest.raises(UserError):
        check.typecheck_and_resolve(SrcFile(None, PREFIX + '''
main=():>int64=>{
    let table=Table[Inner[[42]] []]
    return read(table {table.inner.entries=[42 1] 1})
}
'''))


def test_appending_returns_an_index_into_the_updated_place(tmp_path):
    execute(tmp_path, 'append-index', codegen(SrcFile(None, APPEND), debug_locations=False))


@pytest.mark.parametrize('source', [
    APPEND.replace('    return id\n}', '    return table.entries.length\n}'),
    APPEND.replace('    let id=intern(@table 42)\n    return table.entries[id]',
                   '    return table.entries[intern(@table 42)]'),
])
def test_append_bound_does_not_prove_an_invalid_or_earlier_index(source):
    with pytest.raises(UserError):
        check.typecheck_and_resolve(SrcFile(None, source))


def index_snapshot_source(type_, initial, replacement):
    return f"""
Table:type=[entries:{type_}]
clear=(@table:Table):>addr<i=>i =? 0>=>{{table.entries={replacement} return 0}}
main=():>int64=>{{
    let table=Table[{initial}]
    $runtime_assert table.entries.length =? 1
    let item=table.entries[clear(@table)]
    return if item =? {"42" if type_.startswith("array") else "'x'"} 42 else 1
}}
"""


@pytest.mark.parametrize('type_, initial, replacement', [
    ('array<int64>', '[42]', '[]'),
    ('array<int64>', '[42].copy()', '[7].copy()'),
    ('string', "'x'", "''"),
    ('string', "'x'.copy()", "'y'.copy()"),
])
def test_index_keeps_the_sequence_length_observed_before_its_operand(tmp_path, type_, initial, replacement):
    body = index_snapshot_source(type_, initial, replacement)
    execute(tmp_path, 'index-snapshot', codegen(SrcFile(None, body), debug_locations=False))


def test_index_snapshots_elements_before_in_place_mutation(tmp_path):
    body = index_snapshot_source('array<int64>', '[42].copy()', '[]').replace(
        'table.entries=[]', '$runtime_assert table.entries.length >? 0 table.entries[0]=7')
    execute(tmp_path, 'index-in-place', codegen(SrcFile(None, body), debug_locations=False))


def test_indexed_string_survives_releasing_a_dynamic_receiver(tmp_path):
    body = index_snapshot_source('string', "make('x')", "make('y')")
    body = "make=(s:string):>string=>s+s\n" + body
    body = body.replace('table.entries.length =? 1', 'table.entries.length =? 2')
    body = body.replace('    return if item', "    let churn=make('z')\n    if churn not=? 'zz' return 2\n    return if item")
    execute(tmp_path, 'dynamic-indexed-string', codegen(SrcFile(None, body), debug_locations=False))
