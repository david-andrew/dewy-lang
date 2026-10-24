"""A range census preserves exact broadcast arithmetic and scalar failures."""
import subprocess
import platform
import re

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_broadcast_range_guard_and_fallback(compiler, tmp_path, release):
    source = tmp_path / 'map.dewy'
    source.write_text(('''
f=(xs:array<int64> ys:array<int64>):>array<int64>=>xs .* ys .- xs
main=(args:array<string>)=>{
let x=int64(to_int(args[1]) ?? 0)
let y=int64(to_int(args[2]) ?? 0)
let xs:array<int64>=[loop i in [0..32) x]
let ys:array<int64>=[loop i in [0..32) y]
printl(f(xs ys))
}
''') + "\n$runtime_checks\n")
    binaries = []
    for debug in [False, True]:
        binary = tmp_path / ('scalar' if debug else 'guarded')
        built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                                *(['--release'] if release else []), *(['-g'] if debug else [])],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        if not debug and platform.machine().lower() in ("x86_64", "amd64"):
            body = next(b for b in re.split(r"^fn ", built.stdout, flags=re.M) if b.startswith("f_f_"))
            assert " = vld " in body, body
        binaries.append(binary)
    for x, y in [(1, 3), (-7, 11), (2**30-1, -2**30), (2**30, 1),
                 (2**63-1, 1), (-2**63, 0), (-2**63, -1), (2**63-1, 2)]:
        runs = [subprocess.run([b, str(x), str(y)], capture_output=True, text=True) for b in binaries]
        expected = x*y-x
        for run in runs:
            assert (run.returncode == 0) == (-2**63 <= expected < 2**63), (x, y, run.stderr)
        assert runs[0].stdout == runs[1].stdout


@pytest.mark.parametrize('release', [False, True])
def test_broadcast_rows_preserve_cancellation(compiler, tmp_path, release):
    source = tmp_path / 'rows.dewy'
    source.write_text(('''
f=(m:array<int64 length=[4 4]> bias:array<int64> shift:array<int64> r:int64):>array<int64>=>{
    let h=max.(m .+ bias[new ..] .+ shift[.. new] .- r 0)
    return h.data
}
main=(args:array<string>)=>{
let x=int64(to_int(args[1]) ?? 0)
let y=int64(to_int(args[2]) ?? 0)
let z=int64(to_int(args[3]) ?? 0)
let m=reshape([loop i in [0..16) x] 4 4)
let b:array<int64>=[loop i in [0..4) y]
let s:array<int64>=[loop i in [0..4) z]
printl(f(m b s 3))
}
''') + "\n$runtime_checks\n")
    binaries = []
    for debug in [False, True]:
        binary = tmp_path / ('scalar' if debug else 'guarded')
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else []), *(['-g'] if debug else [])],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        binaries.append(binary)
    for x, y, z in [(1, 3, 7), (-7, 11, 2), (2**30-1, -2**30, 4),
                    (2**63-1, 7, -7), (-2**63, -5, 8), (2**63-1, 7, 0)]:
        runs = [subprocess.run([b, str(x), str(y), str(z)], capture_output=True, text=True) for b in binaries]
        expected = x+y+z-3
        for run in runs:
            assert (run.returncode == 0) == (-2**63 <= expected < 2**63), (x, y, z, run.stderr)
        assert runs[0].stdout == runs[1].stdout
