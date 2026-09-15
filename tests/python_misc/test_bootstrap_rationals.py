"""Exact rational value boundaries and source-library arithmetic agree."""
from test_bootstrap_structural_text import build_program_driver, check_structural_text
from test_bootstrap_lowering import ROOT

CASES = [
    'let main=():>int64=>{let q:rational<int64>=1/3 return if q.numerator+q.denominator=?4 42 else 0}',
    'let main=():>int64=>{let q:rational=2/4 return if q=?1/2 42 else 0}',
    'let main=():>int64=>{let q:rational=0/7 return if q=?0 42 else 0}',
    'let main=():>int64=>{let q:rational=123456789012345678901234567890/7 return if q=?123456789012345678901234567890/7 42 else 0}',
    'let ratio=(a:int64 b:int64 & ~0):>rational=>a/b\nlet main=():>int64=>if ratio(2 6)=?1/3 42 else 0',
    'let ratio=(a:bigint b:bigint & ~0):>rational=>a/b\nlet main=():>int64=>if ratio(2 6)=?1/3 42 else 0',
    'let main=():>int64=>{let q:rational=1/3 let r:rational=1/6 return if q+r=?1/2 and q-r=?1/6 and q*r=?1/18 and -q=?-1/3 42 else 0}',
    'let divide=(a:rational b:rational):>rational=>{if b=?0 return 0 return a/b}\nlet main=():>int64=>if divide(1/3 1/2)=?2/3 and divide(1/3 0)=?0 42 else 0',
    'let printl=(s:string):>int64=>42\nlet main=():>int64=>printl"{21+21}"',
    'let calls:int64=0\nlet next=():>int64=>{calls+=1 return calls}\nlet main=():>int64=>{printl"{next()}:{next()}" return if calls=?2 42 else 0}',
    (ROOT / 'dewy/tests/rationals.dewy').read_text().replace('return checks - 76', 'return if checks=?127 42 else 0'),
]
OUTPUTS = [''] * 9 + ['1:2\n', '5/6 10 -93/10 2/3 -2/3\n']
EXTRA_CASES = [
    'let main=():>int64=>{let a:rational<int64>=1/3 let b=a+2 if b is? Overflow return 0 return if b.numerator=?7 and b.denominator=?3 42 else 0}',
    'let main=():>int64=>{let a:rational<int64>=1/3 let b:rational=1/6 return if a+b=?1/2 42 else 0}',
    'let main=():>int64=>{let a:rational<int64>=6/(-8) return if a.numerator=?-3 and a.denominator=?4 42 else 0}',
    'let divide=(a:rational<int64> b:rational<int64>):>rational<int64>|Overflow=>{if b.numerator=?0 return [numerator=0 denominator=1] return a/b}\nlet main=():>int64=>{let q=divide(1/3 1/6) if q is? Overflow return 0 return if q.numerator=?2 and q.denominator=?1 42 else 0}',
]
CASES += EXTRA_CASES
OUTPUTS += [''] * len(EXTRA_CASES)
ERRORS = [
    # Arithmetic promotions do not introduce new implicit storage conversions.
    'let f=(x:int64):>rational=>x',
    'let f=(x:rational<int64>):>rational=>x',
    'let f=(x:rational):>rational<int64>=>x',

    'let q:rational<int64>=123456789012345678901234567890/7',
    'let q:rational<int64>=1/123456789012345678901234567890',
    'let divide=(a:rational b:rational):>rational=>a/b',
    'let divide=(a:int64 b:int64):>rational=>a/b',
    'let q:rational=1/0',
]

def test_native_rational_boundaries(tmp_path):
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS, outputs=OUTPUTS)
