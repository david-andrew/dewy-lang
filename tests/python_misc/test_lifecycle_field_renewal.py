"""Replacing a transferred component starts a new independently owned lifetime."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute
from test_lifecycle_field_returns import PRELUDE

CASES=[
    PRELUDE+'''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let first=pair.first
pair.first=Token[3] return if first.id=?1 and pair.first.id=?3 and trace=?0 42 else 1}
main=():>int64=>{let result=work() return if trace=?123 result else 2}''',
    PRELUDE+'''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let first=pair.first
pair.first=Token[3] let next=pair.first pair.first=Token[4]
return if first.id+next.id+pair.first.id=?8 42 else 1}
main=():>int64=>{let result=work() return if trace=?3124 result else 2}''',
    PRELUDE+'''Tree:type=[pair:Pair last:Token]
work=():>int64=>{let tree=Tree[Pair[Token[1] Token[2]] Token[3]] let first=tree.pair.first
tree.pair=Pair[Token[4] Token[5]]
return if trace=?2 and first.id=?1 and tree.pair.first.id=?4 42 else 1}
main=():>int64=>{let result=work() return if trace=?21354 result else 2}''',
    PRELUDE+'''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let first=pair.first
pair=Pair[Token[3] Token[4]] return if trace=?2 and first.id=?1 and pair.first.id=?3 42 else 1}
main=():>int64=>{let result=work() return if trace=?2143 result else 2}''',
    PRELUDE+'''take=():>Pair=>{let pair=Pair[Token[1] Token[2]] let first=pair.first
pair.first=Token[3] return pair}
work=():>int64=>{let pair=take() return if trace=?1 and pair.first.id=?3 42 else 1}
main=():>int64=>{let result=work() return if trace=?123 result else 2}''',
    PRELUDE+'''Moved=type of [token:Token
$__drop__ release=():>void=>{trace=trace*10+9}
$__move__ relocate=():>Moved=>Moved[Token[4]]]
Box:type=[value:Moved other:Token]
work=():>int64=>{let box=Box[Moved[Token[1]] Token[2]] let item=box.value
box.value=Moved[Token[3]] return if trace=?1 and item.token.id=?4 42 else 1}
main=():>int64=>{let result=work() return if trace=?194293 result else 2}''',
    PRELUDE+'''Box:type=[items:array<Token> other:Token]
work=():>int64=>{let box=Box[[Token[1]] Token[2]] let items=box.items
box.items=[Token[3]] return if items.length=?1 and box.items.length=?1 42 else 1}
main=():>int64=>{let before=_arena_live_bytes let count:int64=0
loop count<?100 {trace=0 if work() not=?42 or trace not=?123 return 1 count+=1}
return if _arena_live_bytes=?before 42 else 2}''',
    PRELUDE+'''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let first=pair.first
pair.first=Token[pair.second.id+1] return if first.id=?1 and pair.first.id=?3 42 else 1}
main=():>int64=>{let result=work() return if trace=?123 result else 2}''',
]
CASES += [
    PRELUDE+'''work=(flag:bool):>int64=>{let pair=Pair[Token[1] Token[2]] let first=pair.first
if flag return if first.id=?1 42 else 1
pair.first=Token[3] return if pair.first.id=?3 42 else 1}
main=():>int64=>{let result=work(true) return if trace=?12 result else 2}''',
    PRELUDE+'''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let first=pair.first let second=pair.second
pair=Pair[Token[3] Token[4]] return if first.id+second.id+pair.first.id=?6 42 else 1}
main=():>int64=>{let result=work() return if trace=?2143 result else 2}''',
]

ERRORS=[
    PRELUDE+'''work=(pair:Pair):>int64=>{let first=pair.first pair.first=Token[pair.first.id] return first.id}''',
    PRELUDE+'''work=(pair:Pair flag:bool):>int64=>{let first=pair.first if flag pair.first=Token[3] return first.id+pair.first.id}''',
    PRELUDE+'''work=(pair:Pair):>int64=>{let first=pair.first let old=pair.first.id pair.first=Token[3] return first.id+old}''',
    PRELUDE+'''work=(@pair:Pair):>int64=>{let first=pair.first pair.first=Token[3] return first.id}''',
    PRELUDE+'''work=(pair:Pair):>int64=>{let alias=pair let first=pair.first pair.first=Token[3] return alias.first.id+first.id}''',
]

@pytest.mark.parametrize('source',CASES)
def test_field_renewal(source,tmp_path):
    execute(tmp_path,'field-renewal',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_field_renewal_requires_an_unobserved_old_lifetime(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source))

def test_native_field_renewal(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
