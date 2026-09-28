"""Dictionary stores participate in the same last-use proof as array stores."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
build=():>dict<int64 dict<int64 int64>>=>{
    let result:dict<int64 dict<int64 int64>>=[]
    loop index in 0..4 {
        let entry:dict<int64 int64>=[]
        entry[0]=42
        result[index]=entry
    }
    return result
}
main=():>int64=>{
    {let warm=build()}
    let before=_arena_live_bytes
    loop repeat in 0..49 {
        let entries=build()
        if entries.length not=?5 return 1
        loop index in 0..4 {
            if index not in? entries return 2
            if 0 not in? entries[index] return 3
            if entries[index].get(0 0) not=?42 return 4
        }
    }
    return if _arena_live_bytes=?before 42 else 5
}
'''
CASES = [SOURCE, SOURCE.replace('result[index]=entry', 'result[index]=[0->9]\n        result[index]=entry')]
# Later reads, repeated use across loop iterations, and live views all keep
# the independent source alive. COW is not a proof of a free logical copy.
ERRORS = [SOURCE.replace('result[index]=entry', text) for text in [
    'result[index]=entry\n        $runtime_assert entry[0]=?42',
    'const loan=@entry\n        result[index]=entry\n        $runtime_assert loan.get(0 0)=?42',
    'loop inner in 0..2 {result[index]=entry}',
]]

ASSIGN = '''$explicit_copies
Box:type=[items:array<int64>]
let run=():>int64=>{
    let result=Box[[9]]
    loop index in 0..49 {
        let replacement=Box[[42]]
        result=replacement
    }
    return if result.items.length=?1 result.items[0] else 0
}
main=():>int64=>{
    run();
    let before=_arena_live_bytes
    loop repeat in 0..49 {if run() not=?42 return 1}
    return if _arena_live_bytes=?before 42 else 2
}
'''
CASES += [ASSIGN, ASSIGN.replace('Box:type=[items:array<int64>]', 'Box:type=[items:set<int64>]').replace('Box[[9]]', 'Box[set[9]]').replace('Box[[42]]', 'Box[set[42]]').replace('return if result.items.length=?1 result.items[0] else 0', 'return if 42 in? result.items 42 else 0')]
ERRORS += [ASSIGN.replace('result=replacement', 'result=replacement\n        $runtime_assert replacement.items.length=?1')]


@pytest.mark.parametrize('source', CASES)
def test_dictionary_value_moves(tmp_path, source):
    execute(tmp_path, 'dictionary-value-moves', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_dictionary_value_keeps_live_source(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_dictionary_value_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
