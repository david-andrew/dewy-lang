"""Generated int arrays retain exact outliers around their guarded word maps."""
import os
import platform
import re
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_tagged_map_words_and_big_fallback(compiler, tmp_path, release):
    source = tmp_path / 'maps.dewy'
    source.write_text('''$runtime_checks
f=(a:array<int> b:array<int>):>array<int>=>a .* b .+ a
main=(args:array<string>)=>{
 let n=int64(to_int(args[1]) ?? 0)
 let x=to_int(args[2]) ?? 0
 let a:array<int>=[loop i in [0..n) x+i]
 let b:array<int>=[loop i in [0..n) 2]
 printl(f(a b))
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
            assert 'vst ' in body, body
        binaries.append(binary)
    for n in (0, 1, 7, 8, 9, 17, 33):
        for x in (-11, 2**61-1, -2**63, 2**130, -2**130):
            expected = [(x+i)*3 for i in range(n)]
            for binary, sse in ((binaries[0], False), (binaries[0], True), (binaries[1], False)):
                env = dict(os.environ, DEWY_NO_AVX='1') if sse else dict(os.environ)
                if not sse: env.pop('DEWY_NO_AVX', None)
                ran = subprocess.run([binary, str(n), str(x)], capture_output=True, text=True, env=env)
                assert ran.returncode == 0, ran.stderr
                assert list(map(int, ran.stdout.strip()[1:-1].split())) == expected
