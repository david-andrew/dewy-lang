"""Proofs the strict lane needs from visible code (ladder rung 112): a conditional loop is no
hidden cost, a range loop keeps the relation it preserves between two scalars it changes, a
difference of related values is bounded by their rows, a refined integer converts to a float
within its bounds, `to_int` with a small literal digit limit cannot fail, and an
explicit-allocation-failure frame is allocation."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, command='run'):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, command, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


MAIN = 'main = ():>(void | OutOfMemory) & no panics => {\n'

# An insertion sort whose inner `loop cond { }` is visible control flow, every index proven.
SORT = '''$bulletproof
const capacity = 8
sort_prefix = (@xs:array<int32 length=8> n:int64<c => 0 <=? c and c <=? capacity>):>void & no allocates & no panics => {
    loop i in [1..n) {
        let key = xs[i]
        let j = i
        loop j >? 0 and xs[j - 1] >? key {
            xs[j] = xs[j - 1]
            j -= 1
        }
        xs[j] = key
    }
}
''' + MAIN + '''    let xs:array<int32 length=8> = [5 3 9 1 7 2 8 4]
    sort_prefix(@xs 6)
    loop x in xs print"{x} "
    printl""
}
'''

# Tracking a minimum and a maximum keeps `low <=? high`, so the record's sibling contract
# holds, and `high - low + 1` is a nonzero divisor.
SPAN = '''$bulletproof
Reading:type = int32<r => -100000 <=? r and r <=? 100000>
Span:type = [count:int64<(>? 0)> low:Reading high:Reading<(>=? low)>]
span = (xs:array<Reading length=8> n:int64<c => 1 <=? c and c <=? 8>):>Span => {
    let low:Reading = xs[0]
    let high:Reading = low
    loop i in [0..n) {
        let v = xs[i]
        if v <? low low = v
        if v >? high high = v
    }
    BODY
    Span[n low high]
}
buckets = (s:Span v:Reading):>int64 => {
    let width = int64(s.high) - int64(s.low) + 1
    (int64(v) - int64(s.low))*10 // width
}
''' + MAIN + '''    let s = span([5 3 9 1 7 2 8 4] 8)
    let mean:float64 = float64(s.high)/float64(s.count)
    printl"{s.low} {s.high} {buckets(s 7)} {mean}"
}
'''


@pytest.mark.core_quick
def test_conditional_loop_is_no_hidden_cost(compiler, tmp_path):
    result = run(compiler, tmp_path, SORT)
    assert result.returncode == 0 and result.stdout == '1 2 3 5 7 9 8 4 \n', result.stdout + result.stderr


@pytest.mark.core_quick
def test_range_loop_keeps_preserved_relation(compiler, tmp_path):
    result = run(compiler, tmp_path, SPAN.replace('BODY', ''))
    assert result.returncode == 0 and result.stdout == '1 9 6 1.125\n', result.stdout + result.stderr


@pytest.mark.parametrize('body,expected', [
    # (a store the loop does not guard breaks the relation on some path)
    ('loop i in [0..n) {\n        if xs[i] =? 5 low = 7\n    }', 'cannot prove refinement'),
    # (a break where the relation does not hold leaves the loop without it)
    ('loop i in [0..n) {\n        let v = xs[i]\n        if v >? high {\n            low = v\n            break\n        }\n    }',
     'cannot prove refinement'),
])
def test_range_loop_drops_broken_relation(compiler, tmp_path, body, expected):
    result = run(compiler, tmp_path, SPAN.replace('BODY', body), 'check')
    assert result.returncode != 0 and expected in result.stderr, result.stdout + result.stderr


def test_unrelated_difference_may_be_zero(compiler, tmp_path):
    source = '$bulletproof\nwidth = (a:int32 b:int32):>int64 => 100 // (int64(a) - int64(b) + 1)\n' + MAIN + '    printl(width(3 1))\n}\n'
    result = run(compiler, tmp_path, source, 'check')
    assert result.returncode != 0 and 'cannot prove divisor is nonzero' in result.stderr, result.stdout + result.stderr


# A literal limit of at most 18 digits parses into a word: the same answers, and no big integer
# conversion that could fail.
PARSE = '''$bulletproof
parse = (text:string):>int64 & no panics => {
    let n = to_int(text max_digits=3)
    if n is? NotAnInteger return -1
    if n is? TooManyDigits return -2
    if n <? -999 or n >? 999 return -3
    int64(n)
}
twice = (n:int64<(<? 1000)>):>int64 => n * 2
grow = (n:int64<(<? 100)>):>int64 & allocates => twice(n) + 1
''' + MAIN + '''    let k = grow(3)
    if k is? OutOfMemory return OutOfMemory
    printl"{k} {parse("12")} {parse("-999")} {parse("+7")} {parse("1234")} {parse("12a")} {parse("123a")} {parse("")} {parse("-")} {parse("-0")}"
}
'''


@pytest.mark.core_quick
def test_small_digit_limit_and_allocation_frame(compiler, tmp_path):
    result = run(compiler, tmp_path, PARSE)
    assert result.returncode == 0 and result.stdout == '7 12 -999 7 -2 -1 -1 -1 -1 0\n', result.stdout + result.stderr


def test_digit_limit_answers_match(compiler, tmp_path):
    source = '''show = (text:string lim:int64) => {
    let a = to_int(text max_digits=3)
    let b = to_int(text max_digits=lim)
    printl"{a} {b}"
}
main = () => {
    loop t in ["12" "-999" "1234" "123a" "1234a" "" "-" "--1" "-0" "007" " 1"] show(t 3)
}
'''
    result = run(compiler, tmp_path, source)
    lines = result.stdout.splitlines()
    assert result.returncode == 0 and len(lines) == 11, result.stdout + result.stderr
    assert all(line.split()[0] == line.split()[1] for line in lines), result.stdout


# A closed row bounds panics too: a proven index passes, an unproven one is rejected.
@pytest.mark.parametrize('index,ok', [('i', True), ('i + 2', False)])
def test_closed_row_panics(compiler, tmp_path, index, ok):
    source = f'''$runtime_checks
total = (xs:array<int64 length=4>):>int64 & no_effects => {{
    let t:int64 = 0
    loop i in [0..3) {{
        let v = xs[{index}]
        if v >? -1000 and v <? 1000 t += v
    }}
    t
}}
main = () => printl(total([1 2 3 4]))
'''
    result = run(compiler, tmp_path, source, 'check')
    if ok:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0 and 'effect contract violation' in result.stderr, result.stdout + result.stderr
