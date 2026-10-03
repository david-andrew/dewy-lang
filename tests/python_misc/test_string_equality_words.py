"""String equality compares a word at a time and finishes by bytes.

Lengths around the word size, a difference at every position (in the word
part and in the tail), shared storage and empty strings all decide as byte
equality does."""
from test_scalar_projection import execute
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile

SOURCE = '''text=(n:int64 mark:int64):>string=>{
    let result:string=''
    let i:int64=0
    loop i <? n {
        result=result + (if i =? mark 'x' else 'a')
        i+=1
    }
    return result
}
main=():>int64=>{
    let failures:int64=0
    let n:int64=0
    loop n <=? 19 {
        let base=text(n (-1))
        if base not=? text(n (-1)) failures+=1
        if base not=? base failures+=1
        let mark:int64=0
        loop mark <? n {
            if base =? text(n mark) failures+=1
            mark+=1
        }
        if base =? text(n+1 (-1)) failures+=1
        n+=1
    }
    if 'value' not=? 'value' failures+=1
    if 'value' =? 'length' failures+=1
    if '' not=? text(0 (-1)) failures+=1
    return if failures =? 0 42 else failures
}
'''


def test_string_equality_words(tmp_path):
    execute(tmp_path, 'string-equality', codegen(SrcFile(None, SOURCE), debug_locations=False))


def test_native_string_equality_words(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
