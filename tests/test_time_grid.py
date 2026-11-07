"""quantize, ticks and convert against exact fractions, and division by a time that may be zero."""
from fractions import Fraction
import math
import random
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


def rounded(x, how):
    low = math.floor(x)
    if how == 'floor':
        return low
    if how == 'ceil':
        return math.ceil(x)
    if how == 'toward_zero':
        return math.trunc(x)
    part = x - low
    if part != Fraction(1, 2):
        return low + (1 if part > Fraction(1, 2) else 0)
    if how == 'nearest_even':
        return low if low % 2 == 0 else low + 1
    return low + 1 if x > 0 else low  # nearest_away


HOW = ['nearest_even', 'nearest_away', 'floor', 'ceil', 'toward_zero']


def test_quantize_matches_exact_fractions(compiler, tmp_path):
    rng = random.Random(1852)
    lines = []
    expected = []
    for _ in range(150):
        numerator = rng.randrange(-5000, 5000)
        denominator = rng.choice([1, 2, 3, 4, 7, 10, 1000])
        how = rng.choice(HOW)
        tick = rng.choice([1, 1, 5, 1000])
        written = f'{numerator}*1ns/{denominator}' if numerator >= 0 else f'0ns-{-numerator}*1ns/{denominator}'
        lines.append(f"show({written} '{how}' {tick}ns)")
        exact = Fraction(numerator, denominator)
        count = rounded(exact / tick, how)
        value = count * tick
        expected.append((value, exact - value))
    source = """import p"@lib/time/core.dewy" as core
$runtime_checks
show = (q:rational*Time how:core._Rounding tick:rational*Time) => {
    let r = quantize(q rounding=how tick=tick)
    if r isnt? OffGrid {
        let [value lost] = r
        printl"{core.ns_count(value)} {lost/1ns}"
    }
}
""" + '\n'.join(lines) + '\n'
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    got = ran.stdout.splitlines()
    assert len(got) == len(expected)
    for (value, lost), line in zip(expected, got):
        words = line.split()
        assert int(words[0]) == value, line
        assert Fraction(words[1]) == lost, (line, lost)


def test_ticks_floor_with_a_remainder(compiler, tmp_path):
    source = """let t = instant"2026-10-24T12:00:00Z"
let d = (t + 750ms) - (t + 1s)
let [count left] = d.ticks(1s)
printl"{count} {left}"
let [c2 l2] = ((t + 1s) - t).ticks(1s)
printl"{c2} {l2}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['-1 750ms', '1 0s']


def test_convert_is_exact_or_says_why(compiler, tmp_path):
    source = """let half:float64*Time = 0.5s
let tenth:float64*Time = 0.1s
let nan:float64*Time = (0.0/0.0)*s
printl(convert<Duration>(1500ms))
printl(convert<Duration>(3s))
printl(convert<Duration>(half))
printl(convert<Duration>(1ns/3) is? OffGrid)
printl(convert<Duration>(tenth) is? OffGrid)
printl(convert<Duration>(nan) is? OutOfRange)
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['1500ms', '3s', '500ms', 'true', 'true', 'true']


def test_float_times_quantize(compiler, tmp_path):
    source = """let x:float64*Time = 0.1s
let nan:float64*Time = (0.0/0.0)*s
let r = quantize(x rounding='nearest_even')
if r isnt? OffGrid and r isnt? OutOfRange {
    let [d lost] = r
    printl"{d}"
}
printl(quantize(nan rounding='floor') is? OutOfRange)
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['100ms', 'true']


def test_a_tick_must_be_on_the_grid(compiler, tmp_path):
    ran = run(compiler, tmp_path, "printl(quantize(5ns rounding='floor' tick=1ns/3))\n")
    assert ran.returncode != 0
    assert 'a tick here is a positive whole number of nanoseconds' in ran.stderr


def test_the_off_grid_error_points_to_what_exists(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl(instant"2026-10-24T12:00:00Z" + 1ns/3)\n')
    assert ran.returncode != 0
    assert "quantize(q rounding='nearest_even')" in ran.stderr


def test_a_divisor_that_may_be_zero_is_a_value(compiler, tmp_path):
    source = """let t = instant"2026-10-24T12:00:00Z"
let d = (t + 90minute) - t
let z = d - d
printl"{(d/z) is? OutOfRange} {(d//z) is? OutOfRange} {(d%z) is? OutOfRange}"
printl"{d/1s} {d/2} {d//7} {d//1s} {(d/d) is? OutOfRange}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['true true true', '5400 45min 771428571428ns 5400 false']
    ran = run(compiler, tmp_path, 'let t = instant"2026-10-24T12:00:00Z"\nprintl((t-t)/0s)\n')
    assert ran.returncode != 0
    assert 'this divides by zero' in ran.stderr
