"""Bounded difference qualifiers survive only inductively checked backedges."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

PAIR='''work=(n:int64):>int64=>{
let i:int64=0 let j:int64=7
loop i<?n and j<?int64.max {
$assert j-i=?7
i+=1 j+=1
}
return 42
}
main=():>int64=>work(20)'''
CASES=[
    PAIR,
    PAIR.replace('let i:int64=0 let j:int64=7','let i:int64=7 let j:int64=0').replace('j-i=?7','i-j=?7').replace('j<?int64.max','i<?int64.max'),
    PAIR.replace('let i:int64=0 let j:int64=7','let unrelated:int64=9 let i:int64=0 let j:int64=0').replace('j-i=?7','i=?j').replace('i+=1 j+=1','unrelated+=2 i+=1 j+=1'),
    PAIR.replace('i+=1 j+=1', 'if i%2=?0 {i+=1 j+=1 continue}\ni+=1 j+=1'),
    '''work=(n:int64):>int64=>{
let xs:array<int64>=[42] let ys:array<int64>=[]
let i:int64=0
loop i<?n and i<?int64.max {
$assert xs.length-ys.length=?1
xs.push(i) ys.push(i) i+=1
}
$assert xs.length-ys.length=?1
return 42
}
main=():>int64=>work(20)''',
]
ERRORS=[
    '''work=():>int64=>{
let i:int64=120 let j:int64=120
loop 0<=?i<=?127 and j<?int64.max {
i=(i as int8)+1 j+=1
$assert i=?j
}
return 42
}
main=():>int64=>work()''',
    PAIR.replace('j+=1','j+=2'),
    PAIR.replace('i+=1 j+=1','i+=1 if i>?5 continue\nj+=1'),
    PAIR.replace('let j:int64=7','let j:int64=n'),
    PAIR.replace('let i:int64=0 let j:int64=7','let i:int8=113 let j:int8=120').replace('i<?n and j<?int64.max','i<?127').replace('j-i=?7','j>?i'),
    'change=(@j:int64):>void=>{j+=2}\n'+PAIR.replace('j+=1','change(@j)'),
]

@pytest.mark.parametrize('source', CASES)
def test_loop_difference_is_inductive(source,tmp_path):
    execute(tmp_path,'affine-loop',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_loop_difference_is_not_assumed(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source),debug_locations=False)


def test_native_affine_loop_qualifiers(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
