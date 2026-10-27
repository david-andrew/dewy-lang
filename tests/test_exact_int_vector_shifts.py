"""Qword tag shifts preserve every lane on AVX2 and SSE2, including tails."""
import ast
import os
import platform
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_qword_constant_shifts(compiler, tmp_path, release):
    values = [-2**63, -2**63+1, -2**32-1, -1, 0, 1, 2**31, 2**32+1, 2**63-1]
    functions = []
    expected = []
    for count in (0, 1, 31, 32, 33, 63):
        for op in ('left', 'signed', 'unsigned'):
            expr = {'left': f'xs[i] << {count}', 'signed': f'xs[i] >> {count}',
                    'unsigned': f'int(u64(xs[i]) >> {count})'}[op]
            name = f'f{len(functions)}'
            functions.append(f'''{name} = (xs: int[]) -> int[]:
    out = fill(0, xs.len())
    loop i in [0..xs.len()): out[i] = {expr}
    out
''')
            if op == 'signed': row = [v >> count for v in values]
            elif op == 'unsigned': row = [(v % 2**64) >> count for v in values]
            else: row = [(v << count) % 2**64 for v in values]
            expected.append([v if v < 2**63 else v-2**64 for v in row])
    source = tmp_path / 'shifts.jo'
    source.write_text('\n'.join(functions) + f'main = ():\n    xs: int[] = {values}\n' +
                      ''.join(f'    print(f{i}(xs))\n' for i in range(len(functions))))
    binary = tmp_path / 'shifts'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    if platform.machine().lower() in ('x86_64', 'amd64'):
        for op in (12, 13, 14):
            assert f'c={op} imm=3 ty=4' in built.stdout, built.stdout
            assert f'c={op} imm=3 ty=5' in built.stdout, built.stdout
    for sse in (False, True):
        env = dict(os.environ, DEWY_NO_AVX='1') if sse else dict(os.environ)
        if not sse: env.pop('DEWY_NO_AVX', None)
        ran = subprocess.run([binary], capture_output=True, text=True, env=env)
        assert ran.returncode == 0, ran.stderr
        assert [ast.literal_eval(line) for line in ran.stdout.splitlines()] == expected
