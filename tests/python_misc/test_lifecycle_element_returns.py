"""Returning an element transfers it; reverse cleanup visits the other slots."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute
from test_lifecycle_field_returns import PRELUDE

CASES = [
    PRELUDE + '''take=():>Token=>{let items:array<Token>=[Token[1] Token[2] Token[3]] return items[1]}
work=():>int64=>{let item=take() return if trace=?31 and item.id=?2 42 else 1}
main=():>int64=>{let result=work() return if trace=?312 result else 2}''',
    PRELUDE + '''take=(items:array<Token>):>Token?=>{if items.length>?1 return items[1] return none}
work=():>int64=>{let item=take([Token[1] Token[2] Token[3]])
return if trace=?31 and item isnt? none and item.id=?2 42 else 1}
main=():>int64=>{let result=work() return if trace=?312 result else 2}''',
    PRELUDE + '''take=():>Token=>{let items:array<Pair>=[Pair[Token[1] Token[2]] Pair[Token[3] Token[4]]]
return items[1].first}
work=():>int64=>{let item=take() return if trace=?421 and item.id=?3 42 else 1}
main=():>int64=>{let result=work() return if trace=?4213 result else 2}''',
    PRELUDE + '''Box:type=[items:array<Token> other:Token]
take=():>Token=>{let box=Box[[Token[1] Token[2]] Token[3]] return box.items[0]}
work=():>int64=>{let item=take() return if trace=?32 and item.id=?1 42 else 1}
main=():>int64=>{let result=work() return if trace=?321 result else 2}''',
    PRELUDE + '''let selections:int64=0
select=():>int64<v=>0<=?v and v<?2>=>{selections+=1 return 1}
take=():>Token=>{let items:array<Token>=[Token[1] Token[2]] return items[select()]}
work=():>int64=>{let item=take() return if trace=?1 and item.id=?2 and selections=?1 42 else 1}
main=():>int64=>{let before=_arena_live_bytes let i:int64=0
loop i<?100 {trace=0 selections=0 if work() not=?42 or trace not=?12 return 1 i+=1}
return if _arena_live_bytes=?before 42 else 2}''',
]
CASES += [
    PRELUDE + '''Moved=type of [token:Token
$__drop__ release=():>void=>{trace=trace*10+9}
$__move__ relocate=():>Moved=>Moved[Token[4]]]
take=():>Moved=>{let items:array<Moved>=[Moved[Token[1]] Moved[Token[2]]] return items[0]}
work=():>int64=>{let item=take() return if trace=?921 and item.token.id=?4 42 else 1}
main=():>int64=>{let n=work() return if trace=?92194 n else 2}''',
    PRELUDE + '''take=():>Token?=>{let items:array<array<Token>>=[[Token[1] Token[2]] [Token[3] Token[4]]]
if items[1].length>?0 return items[1][0] return none}
work=():>int64=>{let item=take() return if trace=?421 and item isnt? none and item.id=?3 42 else 1}
main=():>int64=>{let n=work() return if trace=?4213 n else 2}''',
]
ERRORS = [
    PRELUDE + 'take=(@items:array<Token>):>Token?=>{if items.length>?0 return items[0] return none}',
    PRELUDE + 'take=(items:array<Token>):>Token=>items[0]',
    PRELUDE + '''select=(@items:array<Token>):>int64<v=>v=?0>=>{items.clear return 0}
take=():>Token=>{let items:array<Token>=[Token[1] Token[2]] return items[select(@items)]}''',
]

@pytest.mark.parametrize('source', CASES)
def test_owning_element_return(source, tmp_path):
    execute(tmp_path, 'element-return', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_element_return_requires_ownership_and_bounds(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_owning_element_returns(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
