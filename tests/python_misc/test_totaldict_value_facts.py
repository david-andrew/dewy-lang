"""Totality follows a value through factories and storage, without naming it."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

PREFIX = "make=():>totaldict<'a'|'b' int64>=>['a'->20 'b'->22]\n"
CASES = [
    PREFIX + "main=():>int64 & allocates=>(make())['a']+(make())['b']",
    PREFIX + "main=():>int64=>{let table=make() return table['a']+table['b']}",
    PREFIX + "main=():>int64=>{let tables:array<totaldict<'a'|'b' int64>>=[make()] return tables[0]['a']+tables[0]['b']}",
    PREFIX + "Box:type=[table:totaldict<'a'|'b' int64>]\nmain=():>int64=>{let box=Box[make()] return box.table['a']+box.table['b']}",
    PREFIX + "pick=(flag:bool):>totaldict<'a'|'b' int64>|none=>if flag make() else none\nmain=():>int64=>{let table=pick(true) return if table isnt? none table['a']+table['b'] else 0}",
    PREFIX + "read=(key:'a'|'b'):>int64=>(make())[key]\nmain=():>int64=>read('a')+read('b')",
    '''let calls:int64=0
make=():>totaldict<'a' int64>=>{calls+=1 return ['a'->42]}
main=():>int64=>{
    let before:int64=_arena_live_bytes
    loop i in 0.. and i <? 100 {if (make())['a'] not=? 42 return 1}
    return if calls=?100 and _arena_live_bytes=?before 42 else 2
}''',

]
ERRORS = [
    "make=():>totaldict<'a'|'b' int64>=>['a'->42]\nmain=():>int64=>(make())['b']",
    "make=():>dict<'a'|'b' int64>=>['a'->42]\nmain=():>int64=>(make())['b']",
    PREFIX + "main=():>int64=>{let table=make() table.clear return 42}",
    PREFIX + "Box:type=[table:totaldict<'a'|'b' int64>]\nmain=():>int64=>{let box=Box[make()] box.table.clear return 42}",
    PREFIX + "Box:type=[table:totaldict<'a'|'b' int64>]\nmain=():>int64=>{let box=Box[make()] box.table=['a'->42] return 42}",
    "Box:type=[table:totaldict<'a'|'b' int64>]\nmain=():>int64=>{let box=Box[['a'->42]] return 42}",
    PREFIX + "main=():>int64=>{let tables:array<totaldict<'a'|'b' int64>>=[make()] tables[0].pop('a'); return 42}",
    PREFIX + "main=():>int64=>{let tables:array<totaldict<'a'|'b' int64>>=[make()] tables[0]=['a'->42] return 42}",

    "let calls:int64=0\nmake=():>totaldict<'a' int64>=>{calls+=1 return ['a'->42]}\nmain=():>int64 & allocates=>(make())['a']",

]

@pytest.mark.parametrize('source', CASES)
def test_total_dictionary_value_executes(tmp_path, source):
    execute(tmp_path, 'totaldict-value', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_total_dictionary_value_requires_proof(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_total_dictionary_value_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
