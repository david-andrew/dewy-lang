"""Compound arithmetic retains the checked operation and its proof obligations."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''f=(n:int64):>int64=>{if n<?0 return 0
n//=256 $assert n>=?0 return n}
main=():>int64=>f(10752)''',
    '''f=(n:int64):>int64=>{if n<?0 return 0
n%=256 $assert n>=?0 and n<?256 return n}
main=():>int64=>f(298)''',
    '''f=(n:int64):>int64=>{if n<?0 or n>?100 return 0
n*=2 $assert n>=?0 and n<=?200 return n}
main=():>int64=>f(21)''',
    '''f=(n:int64):>int64=>{if n<?0 or n>?100 return 0
n<<=1 $assert n>=?0 and n<=?200 n>>=1 return n}
main=():>int64=>f(42)''',
    '''f=(n:int64 d:int64):>int64=>{if d=?0 return 0 n//=d return n}
main=():>int64=>f(84 2)''',
    '''f=(n:addr):>uint8=>{let remaining=n
loop shift in 0..3 {let byte=(remaining%256) as uint8 remaining//=256}
return (remaining%256) as uint8}
main=():>int64=>if f(0)=?0 42 else 1''',
]
ERRORS = [
    'f=(n:int64):>int64=>{n//=0 return n}',
    'f=(n:int64):>int64=>{n%=0 return n}',
    'f=(n:int64 d:int64):>int64=>{n//=d return n}',
    'f=(n:int64 d:int64):>int64=>{n%=d return n}',
    'f=(n:int64):>int64=>{if n<?0 return 0 n*=2 $assert n>=?0 return n}',
]

@pytest.mark.parametrize('source', CASES)
def test_compound_bounds(tmp_path, source):
    execute(tmp_path, 'compound-bounds', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_compound_obligations(source):
    with pytest.raises(ReportException, match='divisor|assertion'):
        codegen(SrcFile(None, source))

def test_native_compound_bounds(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
