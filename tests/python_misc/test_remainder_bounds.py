"""Proof intervals must contain the runtime remainder, including its sign."""
import itertools
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic.analyze.bounds import Interval, _remainder_interval
from test_scalar_projection import execute

@pytest.mark.parametrize('floor', [False, True])
def test_remainder_bounds_against_integer_oracle(floor):
    intervals = [(a, b) for a in range(-5, 6) for b in range(a, 6)]
    for (a, b), (c, d) in itertools.product(intervals, repeat=2):
        result = _remainder_interval(Interval(a, b), Interval(c, d), floor=floor)
        if result is None:
            continue
        for dividend, divisor in itertools.product(range(a, b+1), range(c, d+1)):
            if divisor == 0:
                continue
            quotient = dividend // divisor if floor else (
                (abs(dividend) // abs(divisor)) * (-1 if (dividend < 0) != (divisor < 0) else 1))
            value = dividend - quotient * divisor
            assert result.lower is None or result.lower <= value, (a,b,c,d,result,value)
            assert result.upper is None or value <= result.upper, (a,b,c,d,result,value)

CASES = [
    'f=(x:int64):>int64=>{let r=x%3 $assert -2<=?r and r<=?2 return r}\nmain=():>int64=>if f(-5)=?-2 and f(5)=?2 42 else 1',
    'f=(x:int64):>int64=>{let r=x%(-3) $assert -2<=?r and r<=?2 return r}\nmain=():>int64=>if f(-5)=?-2 and f(5)=?2 42 else 1',
    'f=(x:int64<v=>v>=?0>):>int64=>{let r=x%3 $assert 0<=?r and r<=?2 return r}\nmain=():>int64=>if f(5)=?2 42 else 1',
]
ERRORS = [
    'f=(x:int64):>int64=>{let r=x%3 $assert r>=?0 return r}',
    'f=(x:int64):>int64=>{let r=x%(-3) $assert r<=?0 return r}',
    'f=(x:int64):>int64=>{let r=x%3 let xs=[42 43 44] return xs[r]}',
]

@pytest.mark.parametrize('source', CASES)
def test_remainder_runtime(tmp_path, source):
    execute(tmp_path, 'remainder', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_remainder_does_not_invent_a_sign(source):
    with pytest.raises(ReportException, match='assertion|index'):
        codegen(SrcFile(None, source))

def test_native_remainder_bounds(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
