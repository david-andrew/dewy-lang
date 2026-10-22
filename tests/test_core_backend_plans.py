"""Complete backend pilots: loop liveness, both register classes and helper expansion."""
import os
import platform
import re
import subprocess

import pytest

from tests.support import compiler

pytestmark = pytest.mark.skipif(platform.machine().lower() not in ('x86_64', 'amd64'),
                                reason='x64 allocation pressure')


def build_run(compiler, source, output, flags):
    env = {**os.environ, 'SLOPPY_EMIT_WORKERS': '1', 'SLOPPY_RASTAT': 'v'}
    built = subprocess.run([compiler, 'build', source, *flags, '-o', output],
                           env=env, capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    run = subprocess.run([output], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout, built.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('count', [2, 28], ids=['low-pressure', 'high-pressure'])
@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']], ids=['default', 'release', 'debug'])
def test_backend_pressure(compiler, tmp_path, count, flags):
    floats = min(count, 18)
    # All values survive calls and nested loops. The large case exceeds both
    # physical register classes; noinline prevents release from erasing the pilot.
    text = '@noinline\nword = (x: int) -> int: x * 3 + 1\n'
    text += '@noinline\nreal = (x: f64) -> f64: x * 2.0 + 0.5\n'
    text += '@noinline\npressure = (seed: int) -> int:\n'
    text += ''.join(f'    v{i} = word(seed + {i})\n' for i in range(count))
    text += ''.join(f'    f{i} = real(f64(seed + {i}))\n' for i in range(floats))
    text += '    total = 0\n    loop i in [0..3):\n        loop j in [0..2):\n            total += word(seed + i + j)\n'
    text += '    return total + ' + ' + '.join(f'v{i}' for i in range(count))
    text += ' + int(' + ' + '.join(f'f{i}' for i in range(floats)) + ')\n'
    text += 'print(pressure(7))\n'
    source = tmp_path / 'pressure.jo'
    source.write_text(text)
    out, log = build_run(compiler, source, tmp_path / 'pressure', flags)
    expected = sum((7 + i + j) * 3 + 1 for i in range(3) for j in range(2))
    expected += sum((7 + i) * 3 + 1 for i in range(count))
    expected += int(sum((7 + i) * 2 + .5 for i in range(floats)))
    assert out.strip() == str(expected)
    row = re.search(r'f_pressure_\d+: spill (\d+), save (\d+); pressure (\d+) gpr (\d+) xmm, loop visits (\d+), expire visits (\d+), spill visits (\d+)', log)
    assert row, log
    spill, saved, gpr, xmm, loops, expired, trials = map(int, row.groups())
    assert gpr <= 11 and xmm <= 13
    assert loops > 0 and expired > 0
    if count == 28:
        assert spill > 0
        if '-g' not in flags:
            assert trials > 0
            if not flags:
                assert saved > 0


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release']], ids=['default', 'release'])
def test_backend_bigint_collection_relocation(compiler, tmp_path, flags):
    source = tmp_path / 'helpers.dewy'
    source.write_text('''grow=(n:int):>int=>n*n+1
main=():>void=>{
 let seed:int=100000000000000000000
 let values:array<int>=[seed grow(seed)]
 let snapshot=values
 values.push(grow(values[1]))
 printl"{snapshot[0]} {snapshot[1]} {snapshot.length} {values.length}"
 printl"{values[2]}"
}
''')
    out, _ = build_run(compiler, source, tmp_path / 'helpers', flags)
    seed = 10**20
    grown = seed * seed + 1
    assert out.split() == [str(seed), str(grown), '2', '3', str(grown * grown + 1)]
