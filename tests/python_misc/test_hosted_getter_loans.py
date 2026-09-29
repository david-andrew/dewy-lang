"""Getter variants lend caller storage, preserving guards and value boundaries."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.backend.udewy.lowering_objects import _ObjectLowering
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/union_getter_borrows.dewy').read_text().replace('const node=forward(nodes i%2)', 'const node=read(nodes i%2)')
RECORD = SOURCE.replace('Left=type of [value:int64 data:array<int64>]', 'Node=type of any & [value:int64]\nLeft=type of Node & [data:array<int64>]').replace('Right=type of [value:int64 words:array<string>]', 'Right=type of Node & [words:array<string>]').replace('Node:type=Left|Right|none\n', '')

@pytest.mark.parametrize('source', [SOURCE, RECORD, *[text.replace('return nodes[id]', 'return nodes[id].copy()') for text in (SOURCE, RECORD)]])
def test_hosted_getter_loans_allocate_nothing(tmp_path, source):
    for result in execute(tmp_path, 'getter-loan', codegen(SrcFile(None,source),debug_locations=False)):
        assert result.stdout == '0\n'


def test_getter_loan_has_an_allocating_control(tmp_path, monkeypatch):
    monkeypatch.setattr(_ObjectLowering,'_borrowed_getter_projection',lambda *_:None)
    for result in execute(tmp_path, 'getter-copy', codegen(SrcFile(None,SOURCE),debug_locations=False)):
        assert int(result.stdout)>0

from test_union_getter_borrows import CASES as UNION_CASES, PREFIX

@pytest.mark.parametrize('source', [text.replace('=forward(', '=read(') for text in UNION_CASES])
def test_direct_getter_loans_keep_value_boundaries(tmp_path, source):
    execute(tmp_path, 'getter-boundary', codegen(SrcFile(None,source),debug_locations=False))


def test_direct_getter_preserves_runtime_guard(tmp_path):
    source=PREFIX+'''main=():>int64=>{
 let nodes:array<Node>=[]
 const node=read(nodes 0)
 return if node is? Left node.value else 1
}'''
    for result in execute(tmp_path, 'getter-guard', codegen(SrcFile(None,source),debug_locations=False),101):
        assert 'assertion' in result.stderr.lower()


def test_returned_record_getter_loan_cannot_consume_its_owner(tmp_path):
    source=RECORD.split('measure=')[0]+'''save=(nodes:array<Node>):>Node=>{
 const value=read(nodes 0)
 return value
}
main=():>int64=>{
 let nodes:array<Node>=[Left[21 [21]]]
 let saved=save(nodes)
 if saved is? Left {saved.data.clear()}
 const original=@nodes[0]
 return if original is? Left and original.data.length>?0 original.value+original.data[0] else 1
}'''
    execute(tmp_path, 'getter-returned-record',codegen(SrcFile(None,source),debug_locations=False))


def test_native_getter_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    binary=build_program_driver(tmp_path)
    cases=[SOURCE,RECORD,*[s.replace('return nodes[id]','return nodes[id].copy()') for s in (SOURCE,RECORD)]]
    check_structural_text(binary,tmp_path,cases=cases,errors=[],outputs=['0\n']*len(cases))
    check_structural_text(binary,tmp_path,cases=[s.replace('=forward(', '=read(') for s in UNION_CASES],errors=[])
