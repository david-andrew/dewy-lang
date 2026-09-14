"""Branded parent payloads retain their runtime identity through union tests."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_optional_family_predicates_and_child_union_reads(tmp_path, target):
    source = tmp_path / 'family.dewy'
    source.write_text('''
Token=$abstract type of [loc:int64]
Left=type of Token & [value:int64]
Right=type of Token & [padding:int64 value:int64]
Other=type of Token & []
Descendant=type of Left & [extra:int64]
let accepts=(node:Token|none):>bool=>node is? Left|Right
let rejects=(node:Token|none):>bool=>node isnt? Left|Right
let misses=(node:Token|int64):>bool=>node isnt? Left
let read=(node:Token|none):>int64=>{if node is? Left|Right return node.value return 0}
let calls:int64=0
let next=():>Token|none=>{calls+=1 return Descendant[0 42 777]}
let main=():>int64=>{
    if not accepts(Left[0 1]) or not accepts(Right[0 999 2]) return 1
    if not accepts(Descendant[0 3 777]) or accepts(Other[0]) or accepts(none) return 2
    if rejects(Left[0 1]) or rejects(Right[0 999 2]) return 3
    if not rejects(Other[0]) or not rejects(none) return 4
    if misses(Left[0 1]) or not misses(Right[0 999 2]) or not misses(0) return 5
    if next() isnt? Left|Right or calls not=?1 return 6
    if read(next()) not=?42 or calls not=?2 return 7
    return read(Left[0 20])+read(Right[0 999 22])+read(none)+read(Other[0])
}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr


FIELD_FAMILY = '''
Token=$abstract type of [loc:int64]
Left=type of Token & [value:int64]
Right=type of Token & [padding:int64 value:int64]
Other=type of Token & []
Box:type=[node:Token]
'''


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_child_view_predicate_uses_converted_tags(tmp_path, target):
    source = tmp_path / 'nested-predicate.dewy'
    source.write_text(FIELD_FAMILY + '''
let read=(node:Token|int64):>int64=>{
    if node is? Left|Right {
        if node is? Left return node.value
        return node.value
    }
    return 0
}
let main=():>int64=>read(Left[0 20])+read(Right[0 999 22])+read(0)
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_child_union_widens_into_parent_union(tmp_path, target):
    source = tmp_path / 'widen.dewy'
    source.write_text(FIELD_FAMILY + '''
Descendant=type of Left & [extra:int64]
let widen=(value:Left|Right):>Token|int64=>value
let read=(node:Token|int64):>int64=>{if node is? Left|Right return node.value return 0}
let main=():>int64=>read(widen(Descendant[0 20 777]))+read(widen(Right[0 999 22]))
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_narrowed_parent_union_returns_owned_children(tmp_path, target):
    source = tmp_path / 'owned.dewy'
    source.write_text('''
Token=$abstract type of [loc:int64]
Left=type of Token & [items:array<int64>]
Right=type of Token & [padding:int64 items:array<int64>]
let select=(node:Token|int64):>Left|Right=>{
    if node is? Left|Right return node
    return Left[0 [0 0]]
}
let main=():>int64=>{
    let original:Token|int64=Left[0 [20 22]]
    let selected=select(original)
    if selected is? Left and selected.items.length>?0 {selected.items[0]=99}
    let again=select(original)
    let values=again.items
    if values.length not=?2 return 1
    return values[0]+values[1]
}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_parent_fields_use_their_proven_child_union(tmp_path, target):
    source = tmp_path / 'fields.dewy'
    source.write_text(FIELD_FAMILY + '''
let read=(box:Box):>int64=>{
    if box.node is? Left|Right {
        let saved=box.node
        return saved.value+box.node.value
    }
    return 0
}
let main=():>int64=>read(Box[Left[0 10]])+read(Box[Right[0 999 11]])+read(Box[Other[0]])
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('mutation', [
    'box.node=Other[0]',
    'box=Box[Other[0]]',
    'replace_node(@box)',
])
def test_parent_field_narrowing_is_invalidated_by_writes(mutation):
    source = FIELD_FAMILY + '''
let replace_node=(@box:Box):>void=>{box.node=Other[0];}
let read=(box:Box):>int64=>{
    if box.node is? Left|Right {
''' + mutation + '''
        return box.node.value
    }
    return 0
}
'''
    with pytest.raises(UserError, match='unknown object field `value`'):
        check.typecheck_and_resolve(SrcFile(None, source))
