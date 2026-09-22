"""Last-use component inputs transfer while their wrappers retain lexical cleanup."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute
from test_lifecycle_field_returns import PRELUDE

CASES = [
    PRELUDE + '''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let selected=pair.first
return if trace=?0 and selected.id=?1 42 else 1}
main=():>int64=>{let result=work() return if trace=?12 result else 2}''',
    PRELUDE + '''take=(token:Token):>int64=>token.id
work=():>int64=>{let pair=Pair[Token[1] Token[2]] let result=take(pair.first)
return if result=?1 and trace=?1 42 else 1}
main=():>int64=>{let result=work() return if trace=?12 result else 2}''',
    PRELUDE + '''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let selected=Pair[pair.first Token[3]]
return if trace=?0 and selected.first.id=?1 42 else 1}
main=():>int64=>{let result=work() return if trace=?312 result else 2}''',
    PRELUDE + '''let selections:int64=0
select=():>int64<v=>0<=?v and v<?2>=>{selections+=1 return 1}
work=():>int64=>{let items:array<Token>=[Token[1] Token[2]] let selected=items[select()]
return if trace=?0 and selected.id=?2 and selections=?1 42 else 1}
main=():>int64=>{let before=_arena_live_bytes let i:int64=0
loop i<?100 {trace=0 selections=0 if work() not=?42 or trace not=?21 return 1 i+=1}
return if _arena_live_bytes=?before 42 else 2}''',
    PRELUDE + '''work=(pair:Pair):>int64=>{let selected=pair.second
return if trace=?0 and selected.id=?2 42 else 1}
main=():>int64=>{let result=work(Pair[Token[1] Token[2]]) return if trace=?21 result else 2}''',
    PRELUDE + '''work=():>int64=>{let items:array<Pair>=[Pair[Token[1] Token[2]] Pair[Token[3] Token[4]]]
let selected=items[1].first return if selected.id=?3 and trace=?0 42 else 1}
main=():>int64=>{let result=work() return if trace=?3421 result else 2}''',
    PRELUDE + '''Moved=type of [token:Token
$__drop__ release=():>void=>{trace=trace*10+9}
$__move__ relocate=():>Moved=>Moved[Token[4]]]
Box:type=[value:Moved other:Token]
work=():>int64=>{let box=Box[Moved[Token[1]] Token[2]] let item=box.value
return if trace=?0 and item.token.id=?4 42 else 1}
main=():>int64=>{let n=work() return if trace=?9421 n else 2}''',
]
CASES += [
    PRELUDE + '''take=(which:bool):>Token=>{let pair=Pair[Token[1] Token[2]] let selected=pair.first
if which return selected
return selected}
work=():>int64=>{let token=take(true) return if trace=?2 and token.id=?1 42 else 1}
main=():>int64=>{let result=work() return if trace=?21 result else 2}''',
    PRELUDE + '''work=():>int64=>{loop i in 0.. and i<?1 {
let pair=Pair[Token[1] Token[2]] let selected=pair.first
if selected.id=?1 break
return 1} return if trace=?12 42 else 2}
main=():>int64=>work()''',
    PRELUDE + '''work=():>int64=>{let pair=Pair[Token[1] Token[2]] const alias=@pair
let old=alias.second.id let selected=pair.first return if selected.id+old=?3 42 else 1}
main=():>int64=>{let result=work() return if trace=?12 result else 2}''',
    PRELUDE + '''work=():>int64=>{let pair=Pair[Token[1] Token[2]] let items:array<Token>=[pair.first]
return if trace=?0 and items[0].id=?1 42 else 1}
main=():>int64=>{let result=work() return if trace=?12 result else 2}''',
]
ERRORS = [
    PRELUDE + 'work=(@pair:Pair):>int64=>{let selected=pair.first return selected.id}',
    PRELUDE + 'work=(pair:Pair):>int64=>{let selected=pair.first return selected.id+pair.first.id}',
    PRELUDE + '''Box=type of [token:Token $__drop__ release=():>void=>{trace=token.id}]
work=(box:Box):>int64=>{let selected=box.token return selected.id}''',
    PRELUDE + '''select=(@items:array<Token>):>int64<v=>v=?0>=>{items.clear return 0}
work=():>int64=>{let items:array<Token>=[Token[1] Token[2]] let selected=items[select(@items)] return selected.id}''',
    PRELUDE + 'work=(pair:Pair):>int64=>{const alias=@pair let selected=pair.first return selected.id+alias.second.id}',
]

@pytest.mark.parametrize('source',CASES)
def test_last_use_component_move(source,tmp_path):
    execute(tmp_path,'component-move',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_component_move_needs_complete_lifetime_proof(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source))

def test_native_component_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
