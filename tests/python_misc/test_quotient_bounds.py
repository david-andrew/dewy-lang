"""Division's proof interval follows the selected runtime rounding convention."""
import itertools
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic.analyze.bounds import Interval, _quotient_interval
from test_scalar_projection import execute

@pytest.mark.parametrize('floor', [False, True])
def test_quotient_against_integer_oracle(floor):
    intervals = [(a,b) for a in range(-5,6) for b in range(a,6)]
    intervals += [(None,-1), (1,None), (None,None), (None,0), (0,None)]
    for (a,b),(c,d) in itertools.product(intervals, repeat=2):
        result = _quotient_interval(Interval(a,b),Interval(c,d),floor=floor)
        if result is None:
            continue
        for numerator,divisor in itertools.product(range(-8 if a is None else a,9 if b is None else b+1),
                                                   range(-8 if c is None else c,9 if d is None else d+1)):
            if divisor == 0:
                continue
            value = numerator//divisor if floor else (abs(numerator)//abs(divisor))*(-1 if (numerator<0)!=(divisor<0) else 1)
            assert result.lower is None or result.lower<=value, (a,b,c,d,result,value)
            assert result.upper is None or value<=result.upper, (a,b,c,d,result,value)

CASES = [
    '''f=(n:int64):>int64=>{if n<?0 or n>?126 return 0 let q=n//(-3)
$assert -42<=?q and q<=?0 return -q}
main=():>int64=>f(126)''',
    '''f=(n:int64):>int64=>{if n<?-126 or n>?0 return 0 let q=n//(-3)
$assert 0<=?q and q<=?42 return q}
main=():>int64=>f(-126)''',
    '''f=(n:int64 d:int64):>int64=>{if n<?-126 or n>?126 or d>?-3 return 0 let q=n//d
$assert -42<=?q and q<=?42 return q}
main=():>int64=>f(-126 (-3))''',
]
ERRORS = [
    '''f=(n:int64):>int64=>{if n<?0 return 0 let q=n//(-3) $assert q>=?0 return q}''',
    '''f=(n:int64):>int64=>{if n<?-5 or n>?-4 return 0 let q=n//3 $assert q=?-2 return q}''',
]

@pytest.mark.parametrize('source',CASES)
def test_quotient_runtime(tmp_path,source):
    execute(tmp_path,'quotient-bounds',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_quotient_rejects_false_facts(source):
    with pytest.raises(ReportException,match='assertion'):
        codegen(SrcFile(None,source))

def test_native_quotient_bounds(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
