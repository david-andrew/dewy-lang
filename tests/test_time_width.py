"""`Instant<width=64>` and a type parameter's default: `Date` is `Date<Gregorian>`."""
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


def test_compact_values(compiler, tmp_path):
    source = """let t = instant"2026-10-24T12:00:00Z"
const packed = convert<Instant<width=64>>(instant"2026-10-24T12:00:00Z")
printl"{packed} {(packed as Instant) =? t}"
const d = convert<Duration<width=64>>(instant"2026-10-24T13:30:00Z" - instant"2026-10-24T12:00:00Z")
printl(d)
printl(packed + d)
printl(packed + 1s)
let c:array<Instant<width=64>> = [packed packed]
printl"{c.length} {c[0] =? packed} {c[0] <? c[1]}"
let w:Instant<width=128> = t
printl(w)
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['2026-10-24T12:00:00Z true', '90min', '2026-10-24T13:30:00Z',
                                       '2026-10-24T12:00:01Z', '2 true false', '2026-10-24T12:00:00Z']


def test_the_edges_of_64_bits_are_values(compiler, tmp_path):
    # J0 plus or minus 2^63 ns: April 2269, September 1684.
    source = """import p"@lib/time/core.dewy" as core
let top = core.instant_at(9223372036854775807)
let past = core.instant_at(9223372036854775808)
let bottom = core.instant_at(-9223372036854775808)
let under = core.instant_at(-9223372036854775809)
printl"{convert<Instant<width=64>>(top) is? OutOfRange} {convert<Instant<width=64>>(past) is? OutOfRange}"
printl"{convert<Instant<width=64>>(bottom) is? OutOfRange} {convert<Instant<width=64>>(under) is? OutOfRange}"
let packed = convert<Instant<width=64>>(top)
if packed isnt? OutOfRange {
    printl((packed + 1s) is? OutOfRange)
    printl((packed - 1s) is? OutOfRange)
}
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['false true', 'false true', 'true', 'false']


def test_a_constant_out_of_range_is_a_compile_error(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'const far = convert<Instant<width=64>>(instant"2300-01-01T00:00:00Z")\nprintl(far)\n')
    assert ran.returncode != 0
    assert 'September 1684 to April 2269' in ran.stderr


def test_a_type_parameter_default(compiler, tmp_path):
    source = """Box:type=<T=int64>[v:T]
let x:Box = Box<int64>[1]
let y:Box<string> = Box<string>["a"]
f = (b:Box):>int64 => b.v
printl"{f(x)} {y.v}"
let d:Date<Gregorian> = date"2026-10-24"
let e:Date = d + 1day
g = (a:Date):>int => a.year
h = (a:Date<Gregorian>):>int64 => a.month
printl"{e} {g(d)} {h(e)} {e =? d}"
"""
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['1 a', '2026-10-25 2026 10 false']


def test_a_parameter_with_no_default_is_still_required(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'Box:type=<T>[v:T]\nlet x:Box = Box<int64>[1]\n')
    assert ran.returncode != 0
    assert "expects 1 type argument(s), got 0" in ran.stderr
    ran = run(compiler, tmp_path, 'let x:Date<Gregorian Gregorian> = date"2026-01-01"\n')
    assert ran.returncode != 0
    assert 'type argument' in ran.stderr
