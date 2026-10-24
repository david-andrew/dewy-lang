"""Unsigned fixed-width stores consume carry, rather than signed overflow."""
import random
import shutil
import subprocess

import pytest

from tests.support import compiler
from tests.test_core import Scripts


@pytest.mark.parametrize('target', ['native', 'arm', 'wasm'])
@pytest.mark.parametrize('release', [False, True])
def test_unsigned_store_flags(compiler, tmp_path, target, release):
    if target == 'arm' and not shutil.which('qemu-aarch64'):
        pytest.skip('qemu-aarch64 is needed for ARM execution')
    if target == 'wasm' and not shutil.which('node'):
        pytest.skip('Node is needed for web execution')
    source = tmp_path / 'unsigned.dewy'
    source.write_text(('''add=(a:uint64 b:uint64):>uint64=>a+b
sub=(a:uint64 b:uint64):>uint64=>a-b
mul=(a:uint64 b:uint64):>uint64=>a*b
main=(args:array<string>)=>{
let a=uint64(to_int(args[2]) ?? 0)
let b=uint64(to_int(args[3]) ?? 0)
if args[1]=?"add" printl(add(a b))
else if args[1]=?"sub" printl(sub(a b))
else printl(mul(a b))
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'unsigned'
    flags = ['--release'] if release else []
    if target != 'native': flags += ['--target', 'aarch64-linux' if target == 'arm' else 'wasm32']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    command = [binary] if target == 'native' else [shutil.which('qemu-aarch64'), binary]
    if target == 'wasm':
        scripts = Scripts(); scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'unsigned.cjs'
        runner.write_text('const dewyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
        command = [shutil.which('node'), runner]
    maximum = 2**64-1
    edges = [0, 1, 2**32, 2**63, maximum]
    pairs = [(a, b) for a in edges for b in edges]
    rng = random.Random(167)
    pairs += [(rng.randrange(2**64), rng.randrange(2**64)) for _ in range(8)]
    for op in ['add', 'sub', 'mul']:
        for a, b in pairs:
            expected = {'add': a+b, 'sub': a-b, 'mul': a*b}[op]
            ran = subprocess.run([*command, op, str(a), str(b)], capture_output=True, text=True)
            if 0 <= expected <= maximum:
                assert ran.returncode == 0 and ran.stdout.strip() == str(expected), (target, op, a, b, ran.stderr, ran.stdout)
            else:
                assert ran.returncode == 101 and not ran.stdout, (target, op, a, b, ran.stderr, ran.stdout)
