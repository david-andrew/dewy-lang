"""Borrowed calls retain facts only with transitive no-write/no-escape proof."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

CASES = [
    '''count=(@xs:array<int64>):>int64=>xs.length
forward=(@xs:array<int64>):>int64=>count(@xs)
main=():>int64=>{let xs:array<int64>=[42] forward(@xs); $assert xs.length=?1 return xs[0]}''',
    '''clone=(@source:array<int64>):>array<int64 length=?source.length>=>{
let result:array<int64>=[] let i:int64=0
loop i<?source.length {result.push(source[i]) i+=1}
return result
}
main=():>int64=>{let xs:array<int64>=[42] let ys=clone(@xs) $assert ys.length=?1 return ys[0]}''',
    '''read=(@value:int64):>int64=>value
main=():>int64=>{let box=[value=42] read(@box.value); $assert box.value=?42 return box.value}''',
    '''count=(... @xs:array<int64>):>int64=>xs.length
main=():>int64=>{let xs:array<int64>=[42] count(xs=@xs); $assert xs.length=?1 return xs[0]}''',
]
ERRORS = [
    '''clear=(@xs:array<int64>):>void=>xs.clear
forward=(@xs:array<int64>):>void=>clear(@xs)
main=():>int64=>{let xs:array<int64>=[42] forward(@xs) return xs[0]}''',
    '''invoke=(@xs:array<int64> f:(@items:array<int64>):>void):>int64=>{
$runtime_assert xs.length>?0
f(@xs) return xs[0]
}''',
    '''set=(@value:int64):>void=>{value=0}
main=():>int64=>{let box=[value=42] set(@box.value) $assert box.value=?42 return 42}''',
    '''let n:int64=42
read=(@xs:array<int64>):>int64=>{n=0 return xs.length}
main=():>int64=>{n=42 let xs:array<int64>=[42] read(@xs); $assert n=?42 return 42}''',
]

@pytest.mark.parametrize('source', CASES)
def test_readonly_calls_retain_facts(tmp_path, source):
    execute(tmp_path, 'readonly-facts', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_writes_and_unknown_calls_still_forget(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_readonly_call_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
