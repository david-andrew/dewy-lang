"""Output differential for the recent vector, fork, and arena lowerings.

The program prints one labelled result per input.  One build per target keeps
the matrix inexpensive while every result is checked against a Python oracle.
"""

import os
import math
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from tests.support import Scripts, compiler, target_name  # noqa: F401


LENGTHS = (*range(18), 31, 32, 33)
SOURCE = r'''
from p"bits.jo" import bits, frombits
$runtime_checks
values=(n:int64 x:int64):>array<int64>=>[loop i in [0..n) x+i%7]
row=(a:NDArray<int64> b:NDArray<int64> c:NDArray<int64>):>array<int64>=>{
    return max.(a .+ b .+ c .- 3 0).data
}
rows=(n:int64 mode:int64):>int64=>{
    let ac=if mode=?1 or mode=?4 1 else n
    let bc=if mode=?2 or mode=?4 1 else n
    let cc=if mode=?3 1 else n
    let a=reshape(values(3*ac -11) 3 ac)
    let b=reshape(values(bc 5) 1 bc)
    let c=reshape(values(3*cc 2) 3 cc)
    let total:int64=0
    loop x in row(a b c) {total+=x}
    return total
}
stencil=(n:int64):>int64=>{
    if n <? 3 return 0
    let a:array<float64>=[loop i in [0..n) (i%13) as float64]
    let b=a.copy()
    loop i in [1..n-1) {b[i]=(a[i-1]+a[i]+a[i+1])*0.25}
    let total:int64=0
    loop x in b {total+=(x*1024.0) as int64}
    return total
}
child=(i:int64):>int64=>{
    if i%3=?0 return i*2
    return i-1
}
forked=(n:int64):>int64=>{
    let parts=[parallel i in [0..n) child(i)]
    let total:int64=parts.length
    loop i in [0..parts.length) {total+=parts[i]*(i+1)}
    return total
}
R:type=[x:float64 y:float64]
fold=(n:int64 mode:int64):>uint64=>{
    let values:array<float64>=if mode=?1 [-0.0 0.0 -0.0 0.0]
        else if mode=?2 [frombits(0x7ff8000000000001) 1.0 -0.0 0.0]
        else if mode=?3 [frombits(0x7ff0000000000000) frombits(0xfff0000000000000) 0.0 -0.0]
        else [10000000000000000.0 1.0 -10000000000000000.0 1.0]
    let rs=[loop i in [0..n) R[values[i%4] (i%7) as float64]]
    let acc:float64=-0.0
    loop p in rs {acc+=p.x}
    return bits(acc)
}
arena_case=(n:int64):>int64=>{
    let scratch=Arena[]
    let result=$allocator(@scratch) {
        let xs:array<int64>=[]
        loop i in [0..n) {xs.push(i%17)}
        let saved=xs
        if n >? 1 {xs[0]=99}
        if n >? 1 {$runtime_assert saved[0]=?0}
        xs
    }
    scratch.reset()
    let total:int64=result.length
    loop x in result {total+=x}
    return total
}
overlap=(n:int64):>int64=>{
    let xs=[loop i in [0..n) i%7]
    loop i in [1..n) {xs[i]=xs[i-1]+xs[i]}
    let total:int64=0
    loop x in xs {total+=x}
    return total
}
negative_stride=(n:int64):>int64=>{
    if n <? 2 return 0
    let m=reshape(values(n 3) 1 n)
    let selected=m[0 [end,end-1..]]
    let total:int64=0
    loop i in [0..selected.data.length) {total+=selected.data[i]*(i+1)}
    return total
}
main=(args:array<string>)=>{
    if args.length >? 2 and args[1]=?"overflow" {
        let edge=int64(to_int(args[2]) ?? 0)
        printl(edge+1)
        return
    }
    loop n in [0..18) {
        loop mode in [0..5) {printl"row:{n}:{mode}:{rows(n mode)}"}
        printl"stencil:{n}:{stencil(n)}"
        printl"fork:{n}:{forked(n)}"
        loop mode in [0..4) {printl"fold:{n}:{mode}:{fold(n mode)}"}
        printl"arena:{n}:{arena_case(n)}"
        printl"overlap:{n}:{overlap(n)}"
        printl"negative_stride:{n}:{negative_stride(n)}"
    }
    loop n in [31 32 33] {
        loop mode in [0..5) {printl"row:{n}:{mode}:{rows(n mode)}"}
        printl"stencil:{n}:{stencil(n)}"
        printl"fork:{n}:{forked(n)}"
        loop mode in [0..4) {printl"fold:{n}:{mode}:{fold(n mode)}"}
        printl"arena:{n}:{arena_case(n)}"
        printl"overlap:{n}:{overlap(n)}"
        printl"negative_stride:{n}:{negative_stride(n)}"
    }
    loop n in [4095 4096 4097] {
        printl"arena:{n}:{arena_case(n)}"
        printl"stencil:{n}:{stencil(n)}"
    }
}
'''


def expected():
    out = {}
    for n in LENGTHS:
        for mode in range(5):
            ac, bc, cc = (1 if mode in (1, 4) else n,
                          1 if mode in (2, 4) else n, 1 if mode == 3 else n)
            result = [max(-11 + (i * ac + (j if ac != 1 else 0)) % 7
                          + 5 + (j if bc != 1 else 0) % 7
                          + 2 + (i * cc + (j if cc != 1 else 0)) % 7 - 3, 0)
                      for i in range(3) for j in range(n)]
            out[f'row:{n}:{mode}'] = str(sum(result))
        out[f'fork:{n}'] = str(n + sum((i * 2 if i % 3 == 0 else i - 1) * (i + 1)
                                      for i in range(n)))
        for mode in range(4):
            vals = ((1e16, 1.0, -1e16, 1.0), (-0.0, 0.0, -0.0, 0.0),
                    (float('nan'), 1.0, -0.0, 0.0),
                    (float('inf'), -float('inf'), 0.0, -0.0))[mode]
            acc = -0.0
            for i in range(n):
                acc += vals[i % 4]
            out[f'fold:{n}:{mode}'] = ('nan' if math.isnan(acc) else
                                        str(struct.unpack('<Q', struct.pack('<d', acc))[0]))
        xs = [i % 7 for i in range(n)]
        for i in range(1, n):
            xs[i] = xs[i - 1] + xs[i]
        out[f'overlap:{n}'] = str(sum(xs))
        out[f'negative_stride:{n}'] = str(sum((3 + i % 7) * (n - i)
                                             for i in range(n)) if n >= 2 else 0)
    for n in (*LENGTHS, 4095, 4096, 4097):
        a = [float(i % 13) for i in range(n)]
        b = a.copy()
        if n >= 3:
            for i in range(1, n - 1):
                b[i] = (a[i - 1] + a[i] + a[i + 1]) * 0.25
        out[f'stencil:{n}'] = str(sum(int(x * 1024) for x in b) if n >= 3 else 0)
        xs = [i % 17 for i in range(n)]
        if n >= 2:
            xs[0] = 99
        out[f'arena:{n}'] = str(n + sum(xs))
    return out


@pytest.fixture(scope='module')
def binaries(compiler, tmp_path_factory):
    directory = tmp_path_factory.mktemp('diff_paths')
    source = directory / 'paths.dewy'
    source.write_text(SOURCE)
    (directory / 'bits.jo').write_text(
        'bits = (x: f64) -> u64: f64_bits(x)\n'
        'frombits = (x: u64) -> f64: f64_from_bits(x)\n')
    built = {}
    for name, flags in {'native': (), 'release': ('--release',), 'debug': ('-g',),
                        'wasm': ('--target', 'wasm32'),
                        'arm64': ('--target', target_name('linux-arm64'))}.items():
        if name == 'wasm' and not shutil.which('node'):
            continue
        if name == 'arm64' and not shutil.which('qemu-aarch64'):
            continue
        binary = directory / name
        result = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f'{name}: {result.stdout}{result.stderr}'
        if name == 'wasm':
            scripts = Scripts()
            scripts.feed(binary.with_suffix('.html').read_text())
            runner = directory / 'wasm.cjs'
            runner.write_text('const dewyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
            binary = runner
        built[name] = binary
    return built


def test_differential_paths(binaries):
    want = expected()
    assert len(want) >= 120
    observed = {}
    mismatches = []
    for mode, binary in binaries.items():
        command = ([shutil.which('node'), binary] if mode == 'wasm' else
                   [shutil.which('qemu-aarch64'), binary] if mode == 'arm64' else [binary])
        result = subprocess.run(command, env=dict(os.environ, DEWY_THREADS='2'),
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f'{mode}: {result.stdout}{result.stderr}'
        rows = dict(line.rsplit(':', 1) for line in result.stdout.splitlines())
        assert rows.keys() == want.keys(), (mode, rows.keys() ^ want.keys())
        for case, value in want.items():
            actual = rows[case]
            if value == 'nan':
                bits = int(actual)
                ok = bits & 0x7ff0000000000000 == 0x7ff0000000000000 and bool(bits & 0xfffffffffffff)
            else:
                ok = actual == value
            if not ok:
                mismatches.append((mode, case, rows[case], value))
        observed[mode] = rows
    assert len(observed) == 5, f'Missing target: {observed.keys()}'
    assert not mismatches, (len(mismatches), {m: sum(x[0] == m for x in mismatches)
                                            for m in observed}, mismatches[:8])


def test_differential_checked_overflow(binaries):
    for mode, binary in binaries.items():
        command = ([shutil.which('node'), binary] if mode == 'wasm' else
                   [shutil.which('qemu-aarch64'), binary] if mode == 'arm64' else [binary])
        result = subprocess.run([*command, 'overflow', '9223372036854775807'],
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 101, (mode, result.returncode, result.stdout, result.stderr)
        assert 'overflow' in result.stderr, (mode, result.stderr)
