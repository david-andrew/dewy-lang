"""Shared ambient footprints preserve snapshots and settle recursive callers."""
import os
import subprocess

import pytest
from tests.support import compiler


def build_run(compiler, tmp_path, source, release):
    path = tmp_path / 'consumer.jo'
    path.write_text(source)
    binary = tmp_path / 'consumer'
    result = subprocess.run(
        [compiler, 'build', path, '-o', binary, *(['--release'] if release else [])],
        env=dict(os.environ, DEWY_EMIT_WORKERS='1'),
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('operation', ['g.reserve(10000)', 'g.resize(4)', 'data(g)'])
def test_effect_consumers_recursive_snapshot(compiler, tmp_path, release, operation):
    source = '''g: int[] = [10, 20, 30]
saved: int[] = []
first = (n: int):
    if n > 0: second(n - 1)
second = (n: int):
    if n > 0: first(n - 1)
    else:
        saved = g
        OPERATION
        g[1] = 99
sum = (xs: mut int[]) -> int:
    total = 0
    loop i in [0..3):
        if i == 0: first(1)
        total += xs[i]
    total
main = ():
    print(sum(mut g))
    print(saved)
'''.replace('OPERATION', operation)
    assert build_run(compiler, tmp_path, source, release) == '139\n[10, 20, 30]\n'


@pytest.mark.parametrize('release', [False, True])
def test_effect_consumers_diamond_global_write(compiler, tmp_path, release):
    source = '''g: int[] = [1, 2, 3]
leaf = (): g[1] += 10
left = (): leaf()
right = (): leaf()
join = ():
    left()
    right()
main = ():
    total = 0
    loop i in [0..g.len()):
        if i == 0: join()
        total += g[i]
    print(total)
'''
    assert build_run(compiler, tmp_path, source, release) == '26\n'


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('name,output', [('service', '9 2 42\n'),
                                         ('database', '1 2 1 99\n')])
def test_effect_consumers_projected_mutations(compiler, tmp_path, release, name, output):
    from pathlib import Path
    source = Path(__file__).parent / 'fixtures/effect_consumers' / f'{name}.dewy'
    binary = tmp_path / 'consumer'
    built = subprocess.run(
        [compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
        capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert (ran.returncode, ran.stdout) == (0, output), ran.stderr
