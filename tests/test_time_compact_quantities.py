"""Compact times take the same time quantities as wide ones; the width changes only range and errors."""
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)

PROGRAM = r"""import p"@lib/time/core.dewy" as core
const p=convert<Instant<width=64>>(instant"2026-01-01T00:00:00Z")
printl(p+1ns)
printl(p-1ns)
printl(1ns+p)
printl(p+1s)
printl(1s+p)
printl(p+1s/2)
const d=convert<Duration<width=64>>(instant"2026-01-01T00:00:01Z"-instant"2026-01-01T00:00:00Z")
printl(d+1s)
printl(1s+d)
printl(d-1s)
printl(3s-d)
printl(d+1ns)
printl(1ns+d)
printl(d-1ns)
printl(1s/2-d)
printl(d <? 2s)
printl(2s <? d)
printl(d =? 1s)
printl(d <? 3s/2)
printl(1s/2 <? d)
printl(d =? 1s/2)
f=(q:rational*Time)=>{
    let r=p+q
    printl(if r is? OffGrid {"off"} else {"on"})
}
f(1ns/3)
f(1ns)
let top=convert<Instant<width=64>>(core.instant_at(9223372036854775807))
if top isnt? OutOfRange { printl((top+1ns) is? OutOfRange) printl((top-1ns) is? OutOfRange) printl(core.ns_count(top as Instant)) }
let bottom=convert<Duration<width=64>>(core.duration_of(-9223372036854775808))
if bottom isnt? OutOfRange { printl((bottom-1ns) is? OutOfRange) printl((bottom+1ns) is? OutOfRange) }
"""
OUTPUT = """2026-01-01T00:00:00.000000001Z
2025-12-31T23:59:59.999999999Z
2026-01-01T00:00:00.000000001Z
2026-01-01T00:00:01Z
2026-01-01T00:00:01Z
2026-01-01T00:00:00.5Z
2s
2s
0s
2s
1000000001ns
1000000001ns
999999999ns
-500ms
true
false
true
true
true
false
off
on
true
false
9223372036854775807
true
false
"""


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path)


def test_quantities_and_edges(compiler, tmp_path):
    ran = run(compiler, tmp_path, PROGRAM)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == OUTPUT


def test_a_constant_off_the_grid_is_a_compile_error(compiler, tmp_path):
    for expression in ('p+1ns/3', '1ns/3+p', 'p-1ns/3'):
        ran = run(compiler, tmp_path, f'const p=convert<Instant<width=64>>(instant"2026-01-01T00:00:00Z")\nprintl({expression})\n')
        assert ran.returncode != 0, expression
        assert 'not a whole nanosecond' in ran.stderr
    for expression in ('d+1ns/3', '1ns/3+d', 'd-1ns/3', '1ns/3-d'):
        ran = run(compiler, tmp_path, f'const d=convert<Duration<width=64>>(instant"2026-01-01T00:00:01Z"-instant"2026-01-01T00:00:00Z")\nprintl({expression})\n')
        assert ran.returncode != 0, expression
        assert 'not a whole nanosecond' in ran.stderr
