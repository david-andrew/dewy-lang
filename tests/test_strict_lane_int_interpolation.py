"""Interpolating an integer cannot panic: under `$bulletproof` (`no allocates & no panics` by
default, `& no panics` stated) every integer type formats, plain, with a literal specification,
refined, as a loop counter or as a big `int`."""
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)

SOURCE = '''$bulletproof
Reading:type = int32<r => -100000 <=? r and r <=? 100000>
refined = (r:Reading):>string & allocates & no panics => "r {r}"
specified = (i:int64):>string & allocates & no panics => "{i:5}|{i:>8}|{i:08}|{i:x}"
squared = (n:int):>string & allocates & no panics => {
    let m = n * n
    "{m}"
}
main = ():>(void | OutOfMemory) & no panics => {
    let a:uint64 = 5
    let b:int8 = -3
    let c:uint32 = 9
    let d:int16 = 300
    let e = 7
    printl"{a} {b} {c} {d} {e}"
    loop i in [0..3) printl"i={i}"
    printl(refined(Reading(-5)))
    printl(specified(42))
    printl(squared(12345678901234))
}
'''


def test_strict_lane_int_interpolation(compiler, tmp_path):
    (tmp_path / 'main.dewy').write_text(SOURCE)
    result = subprocess.run([compiler, 'run', 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ('5 -3 9 300 7\ni=0\ni=1\ni=2\nr -5\n   42|      42|00000042|2a\n'
                             '152415787532374345526722756\n'), result.stdout
