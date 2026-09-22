"""Constant array selections can transfer independently without double cleanup."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute
from test_lifecycle_field_returns import PRELUDE

CASES = [
    PRELUDE+'''work=():>int64=>{let xs=[Token[1] Token[2] Token[3]] let first=xs[0]
return if first.id=?1 and xs[1].id=?2 42 else 1}
main=():>int64=>{let result=work() return if trace=?132 result else 2}''',
    PRELUDE+'''work=():>int64=>{let xs=[Token[1] Token[2] Token[3]]
let first=xs[0] let last=xs[2]
return if first.id+last.id+xs[1].id=?6 42 else 1}
main=():>int64=>{let result=work() return if trace=?312 result else 2}''',
    PRELUDE+'''work=():>int64=>{let xs=[Pair[Token[1] Token[2]] Pair[Token[3] Token[4]]]
let first=xs[0].first let second=xs[0].second let last=xs[1].second
return if first.id+second.id+last.id+xs[1].first.id=?10 42 else 1}
main=():>int64=>{let result=work() return if trace=?4213 result else 2}''',
    PRELUDE+'''work=():>int64=>{let xs=[[Token[1] Token[2]] [Token[3] Token[4]]]
let first=xs[0][0] let last=xs[1][1]
return if first.id+last.id+xs[0][1].id+xs[1][0].id=?10 42 else 1}
main=():>int64=>{let before=_arena_live_bytes let result=work()
return if trace=?4132 and _arena_live_bytes=?before result else 2}''',
    PRELUDE+'''Box:type=[items:array<Token> other:Token]
work=():>int64=>{let box=Box[[Token[1] Token[2] Token[3]] Token[4]]
let first=box.items[0] let last=box.items[2]
return if first.id+last.id+box.items[1].id+box.other.id=?10 42 else 1}
main=():>int64=>{let result=work() return if trace=?3142 result else 2}''',
]
CASES += [
    PRELUDE+'''Moved=type of [id:int64
$__drop__ release=():>void=>{trace=trace*10+id}
$__move__ relocate=():>Moved=>Moved[id+10]]
work=():>int64=>{let xs=[Moved[1] Moved[2]] let first=xs[0]
return if first.id=?11 and xs[1].id=?2 42 else 1}
main=():>int64=>{let result=work() return if trace=?112 result else 2}''',
]
ERRORS = [
    PRELUDE+'work=():>int64=>{let xs=[Token[1] Token[2]] let first=xs[0] return first.id+xs[0].id}',
    PRELUDE+'work=():>array<Token>=>{let xs=[Token[1] Token[2]] let first=xs[0] return xs}',
    PRELUDE+'work=():>int64=>{let xs=[Token[1] Token[2]] let first=xs[0] xs.clear return first.id}',
    PRELUDE+'work=(i:int64):>int64=>{let xs=[Token[1] Token[2]] if i<?0 or i>=?2 return 0 let first=xs[0] return first.id+xs[i].id}',
    PRELUDE+'work=(@xs:array<Token length=?2>):>int64=>{let first=xs[0] return first.id+xs[1].id}',
]

@pytest.mark.parametrize('source', CASES)
def test_disjoint_element_ownership(tmp_path,source):
    execute(tmp_path,'disjoint-elements',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source', ERRORS)
def test_disjoint_element_boundaries(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source))

def test_native_disjoint_elements(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
