"""Remainder results retain a live relation to their nonzero divisor."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''read=(xs:array<int64> n:int64):>int64=>{
if xs.length=?0 or n<?0 return 0 let i=n%xs.length return xs[i]}
main=():>int64=>read([1 2 42] 5)''',
    '''read=(xs:array<int64> n:int64):>int64=>{
if xs.length=?0 or n<?0 return 0 return xs[n%xs.length]}
main=():>int64=>read([1 2 42] 5)''',
    '''read=(xs:array<int64> n:int64 limit:int64):>int64=>{
if limit<=?0 or limit>?xs.length or n<?0 return 0
let i=n%limit $assert i<?limit return xs[i]}
main=():>int64=>read([1 2 42 4] 5 3)''',
    '''read=(n:int64 divisor:int64):>int64=>{
if divisor>=?0 return 0 let r=n%divisor $assert divisor<?r return r}
main=():>int64=>if read(-5 (-3))=?-2 42 else 1''',
]
ERRORS = [
    '''read=(divisor:int64):>int64=>{
if divisor<=?0 return 0 divisor=7%divisor $assert divisor<?divisor return divisor}''',
    '''let __mod__=(n:int64 divisor:int64):>int64=>divisor
read=(n:int64 divisor:int64):>int64=>{
if divisor<=?0 return 0 let r=__mod__(n divisor) $assert r<?divisor return r}''',
    '''read=(xs:array<int64> n:int64):>int64=>{
if xs.length=?0 return 0 let i=n%xs.length return xs[i]}''',
    '''read=(n:int64 divisor:int64):>int64=>{
if divisor<=?0 return 0 let r=n%divisor divisor=1 $assert r<?divisor return r}''',
    '''read=(xs:array<int64> n:int64):>int64=>{
if xs.length=?0 or n<?0 return 0 let i=n%xs.length xs.clear return xs[i]}''',
]

@pytest.mark.parametrize('source', CASES)
def test_remainder_relations(tmp_path, source):
    execute(tmp_path, 'remainder-relations', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_invalid_remainder_relations(source):
    with pytest.raises(ReportException, match='assertion|index'):
        codegen(SrcFile(None, source))

def test_native_remainder_relations(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
