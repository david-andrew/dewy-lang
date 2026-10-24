"""Signed and unsigned 32-bit store flags retain the full boundary semantics."""
import itertools
import random
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('kind', ['int32', 'uint32'])
@pytest.mark.parametrize('release', [False, True])
def test_word32_flags(compiler, tmp_path, kind, release):
    source = tmp_path / 'words.dewy'
    source.write_text((f'''add=(a:{kind} b:{kind}):>{kind}=>a+b
sub=(a:{kind} b:{kind}):>{kind}=>a-b
mul=(a:{kind} b:{kind}):>{kind}=>a*b
main=(args:array<string>)=>{{
let a={kind}(to_int(args[2]) ?? 0)
let b={kind}(to_int(args[3]) ?? 0)
if args[1]=?"add" printl(add(a b))
else if args[1]=?"sub" printl(sub(a b))
else printl(mul(a b))
}}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'words'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    low, high = (-2**31, 2**31-1) if kind == 'int32' else (0, 2**32-1)
    edges = sorted({low, low+1, high, high-1, 0, 1, 32768, 65536})
    pairs = list(itertools.product(edges, repeat=2))
    rng = random.Random(32)
    pairs += [(rng.randint(low, high), rng.randint(low, high)) for _ in range(16)]
    for op in ['add', 'sub', 'mul']:
        for a, b in pairs:
            value = {'add': a+b, 'sub': a-b, 'mul': a*b}[op]
            ran = subprocess.run([binary, op, str(a), str(b)], capture_output=True, text=True)
            if low <= value <= high:
                assert ran.returncode == 0 and ran.stdout.strip() == str(value), (op, a, b, ran.stdout, ran.stderr)
            else:
                assert ran.returncode == 101 and not ran.stdout, (op, a, b, ran.stdout, ran.stderr)
