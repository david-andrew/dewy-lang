"""`[a..b)` over ordered values that are not integers: Instant, Date, time, fraction, float, text."""
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


def test_instants(compiler, tmp_path):
    source = """let a = instant"2027-01-01T00:00:00Z"
let b = instant"2028-01-01T00:00:00Z"
printl"{a in? [a..b)} {b in? [a..b)} {b in? [a..b]} {(a+1s) in? (a..b)} {a in? (a..b)}"
let w = [a..b)
printl"{w}"
printl"{w.first} {w.last} {w.includes_first} {w.includes_last} {(a+1s) in? w} {b in? w} {w.is_empty}"
let o:Range<Instant> = (a..b]
printl"{o} {a in? o} {b in? o} {o =? w} {[b..a).is_empty} {(a..a].is_empty} {[a..a].is_empty}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == [
        'true false true true false',
        '[2027-01-01T00:00:00Z..2028-01-01T00:00:00Z)',
        '2027-01-01T00:00:00Z 2028-01-01T00:00:00Z true false true false false',
        '(2027-01-01T00:00:00Z..2028-01-01T00:00:00Z] false true false true true false']


def test_the_same_form_over_other_ordered_values(compiler, tmp_path):
    source = """let r = [1/2..3/2)
printl"{r} {1 in? r} {2 in? r}"
let f:float64 = 0.5
printl"{f in? [0.0..1.0)} {f in? [1.0..2.0)}"
printl"{"m" in? ["a".."n")} {"z" in? ["a".."n")}"
let q = [1s..2s)
printl"{q} {1500ms in? q} {2s in? q}"
let t = instant"2026-10-24T12:00:00Z"
let d = (t + 1500ms) - t
printl"{d in? q} {d in? [2s..3s)}"
printl"{date"2026-06-01" in? [date"2026-01-01"..date"2027-01-01")} {date"2027-01-01" in? [date"2026-01-01"..date"2027-01-01")}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['[1/2..3/2) true false', 'true false', 'true false', '[1s..2s) true false',
                                       'true false', 'true false']


def test_integer_ranges_are_as_they_were(compiler, tmp_path):
    source = """let n:int = 4
let xs = [1 2 3 4]
printl"{3 in? [1..4)} {4 in? [1..4)} {xs[1..3)} {[0..3)} {[1,3..9]} {n in? [0..n]}"
loop i in [0..2) { printl(i) }
let w = [0..n)
printl(w)
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['true false [2 3] [0..2] [1,3..9] true', '0', '1', '[0..3]']


def test_what_a_range_of_points_cannot_do(compiler, tmp_path):
    t = 'let a = instant"2027-01-01T00:00:00Z"\n'
    ran = run(compiler, tmp_path, t + 'loop x in [a..a+5s) { printl(x) }\n')
    assert ran.returncode != 0
    assert 'a range counts in whole numbers, not Instant' in ran.stderr
    ran = run(compiler, tmp_path, t + 'let s = [a, a+1s..a+5s)\n')
    assert ran.returncode != 0
    assert 'only a range of integers has a step for now' in ran.stderr


def test_generic_conversion_prints_a_generic_record(compiler, tmp_path):
    source = 'Box:type = <T>[v:T]\n__as__ = <T>(b:Box<T>):>string => "box {b.v}"\nprintl(Box<int64>[3])\nprintl("{Box<string>["x"]}")\n'
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['box 3', 'box x']
