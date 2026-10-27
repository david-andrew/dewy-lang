"""The tagged sum census validates operands before using its modular trial sum."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_tagged_sum_census_and_exact_fallback(compiler, tmp_path, release):
    source = tmp_path / 'sum.dewy'
    source.write_text('''$runtime_checks
main=(args:array<string>)=>{
 let xs:array<int>=[]
 loop i in [1..args.length) {xs.push(to_int(args[i]) ?? 0)}
 printl(sum(xs))
}
''')
    binary = tmp_path / 'sum'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    cases = [[], [0], list(range(-33, 34)), [2**31-1]*33, [-2**31]*33,
             [2**31]*33, [-2**31-1]*33, [2**62-1, -2**62, 3],
             [2**100, -2**100, 7], [2**100]*9, [-2**100]*17]
    for values in cases:
        for sse in (False, True):
            env = dict(os.environ, DEWY_NO_AVX='1') if sse else dict(os.environ)
            if not sse: env.pop('DEWY_NO_AVX', None)
            ran = subprocess.run([binary, *map(str, values)], capture_output=True, text=True, env=env)
            assert ran.returncode == 0, ran.stderr
            assert ran.stdout == f'{sum(values)}\n'
