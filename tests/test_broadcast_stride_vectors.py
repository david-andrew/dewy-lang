"""Guarded row maps specialize strides without changing exact arithmetic."""
import ast
import os
import platform
import random
import re
import subprocess

import pytest

from tests.support import compiler


def run(binary, *args, sse=False):
    env = {k: v for k, v in os.environ.items() if k != 'DEWY_NO_AVX'}
    if sse:
        env['DEWY_NO_AVX'] = '1'
    return subprocess.run([binary, *map(str, args)], env=env, capture_output=True, text=True)


@pytest.mark.parametrize('release', [False, True])
def test_broadcast_stride_cases_and_exact_fallback(compiler, tmp_path, release):
    source = tmp_path / 'rows.dewy'
    source.write_text('''$runtime_checks
f=(a:NDArray<int64> b:NDArray<int64> c:NDArray<int64>):>array<int64>=>{
    let h=max.(a .+ b .+ c .- 3 0)
    return h.data
}
values=(n:int64 x:int64):>array<int64>=>[loop i in [0..n) x+i%7]
main=(args:array<string>)=>{
    let n=int64(to_int(args[1]) ?? 0)
    let mode=int64(to_int(args[2]) ?? 0)
    let x=int64(to_int(args[3]) ?? 0)
    let y=int64(to_int(args[4]) ?? 0)
    let z=int64(to_int(args[5]) ?? 0)
    let ac=if mode=?1 or mode=?4 1 else n
    let bc=if mode=?2 or mode=?4 1 else n
    let cc=if mode=?3 1 else n
    let a=reshape(values(3*ac x) 3 ac)
    let b=reshape(values(bc y) 1 bc)
    let c=reshape(values(3*cc z) 3 cc)
    printl(f(a b c))
}
''')
    binaries = []
    for debug in (False, True):
        binary = tmp_path / ('scalar' if debug else 'vectors')
        built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                                *(['--release'] if release else []), *(['-g'] if debug else [])],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        if not debug and platform.machine().lower() in ('x86_64', 'amd64'):
            body = next(b for b in re.split(r'^fn ', built.stdout, flags=re.M) if b.startswith('f_f_'))
            assert re.search(r' = vbin .*c=5 imm=3 ty=5', body), body
            assert re.search(r' = vbin .*c=5 imm=3 ty=4', body), body
        binaries.append(binary)
    for n in (0, 1, 2, 3, 4, 7, 8, 9, 15, 17, 33):
        for mode in range(5):  # unit, each single splat, and two splats (fallback)
            ac, bc, cc = (1 if mode in (1, 4) else n,
                          1 if mode in (2, 4) else n, 1 if mode == 3 else n)
            expected = [max(-11 + (i*ac + (j if ac != 1 else 0)) % 7
                            + 5 + (j if bc != 1 else 0) % 7
                            + 2 + (i*cc + (j if cc != 1 else 0)) % 7 - 3, 0)
                        for i in range(3) for j in range(n)]
            for binary, sse in ((binaries[0], False), (binaries[0], True), (binaries[1], False)):
                ran = run(binary, n, mode, -11, 5, 2, sse=sse)
                assert ran.returncode == 0, ran.stderr
                assert list(map(int, ran.stdout.strip()[1:-1].split())) == expected, (n, mode)
    # Census outliers must keep exact cancellation, and fail only at the same
    # final fixed-width store as the scalar reference. Input setup fits a word.
    for xyz in ((2**63-10, 20, -20), (-2**63, -20, 30), (2**63-10, 20, 0)):
        for mode in range(5):
            scalar = run(binaries[1], 17, mode, *xyz)
            for sse in (False, True):
                vector = run(binaries[0], 17, mode, *xyz, sse=sse)
                assert (vector.returncode == 0) == (scalar.returncode == 0)
                assert vector.stdout == scalar.stdout


@pytest.mark.parametrize('release', [False, True])
def test_signed_qword_minmax_vectors(compiler, tmp_path, release):
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('native vector backend requires x86-64')
    edge = [-2**63, -2**63+1, -2**32-1, -2**32, -1, 0, 1,
            2**31-1, 2**31, 2**32-1, 2**32, 2**32+1, 2**63-1]
    pairs = [(a, b) for a in edge for b in edge]
    rng = random.Random(2652000)
    pairs += [(rng.randrange(-2**63, 2**63), rng.randrange(-2**63, 2**63)) for _ in range(128)]
    xs, ys = map(list, zip(*pairs))
    functions = '\n'.join(f'''f{k} = (xs: int[], ys: int[]) -> int[]:
    out = fill(0, xs.len())
    loop i in [0..xs.len()):
        a = xs[i]
        b = ys[i]
        out[i] = if a {cmp} b: a else: b
    out
''' for k, cmp in enumerate(('>', '<', '>=', '<=')))
    source = tmp_path / 'minmax.jo'
    source.write_text(functions + f'''main = ():
    xs: int[] = {xs}
    ys: int[] = {ys}
''' + ''.join(f'    print(f{k}(xs, ys))\n' for k in range(4)))
    binary = tmp_path / 'minmax'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for op in (4, 5):
        for ty in (4, 5):
            assert re.search(rf' = vbin .*c={op} imm=3 ty={ty}', built.stdout)
    expected = [[operation(a, b) for a, b in pairs] for operation in (max, min, max, min)]
    for sse in (False, True):
        ran = run(binary, sse=sse)
        assert ran.returncode == 0, ran.stderr
        assert [ast.literal_eval(line) for line in ran.stdout.splitlines()] == expected
