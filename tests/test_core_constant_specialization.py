"""Constant entry controls specialize bounded callees without changing dynamic calls."""
import re
import subprocess

import pytest

from tests.support import compiler


SOURCE = '''@noinline
opaque = (x: int) -> int: x * 3 + 1
{annotation}choose = (mode: int, x: int) -> int:
    if mode == 0: return x + 7
    if mode == 1: return opaque(x) + opaque(x + 1)
    if mode == 2: return opaque(x * 2) - opaque(x - 1)
    if mode == 3: return opaque(x + 9) * 2
    return opaque(x - 1)
@noinline
work = (x: int) -> int: choose(0, x) + choose(2, x) + choose(x & 3, x)
loop x in [-3, 0, 1, 2, 7]: print(work(x))
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release'], ['--release', '-g']])
@pytest.mark.parametrize('noinline', [False, True])
def test_constant_control_and_dynamic_fallback(compiler, tmp_path, flags, noinline):
    source = tmp_path / 'specialize.jo'
    source.write_text(SOURCE.format(annotation='@noinline\n' if noinline else ''))
    binary = tmp_path / 'specialize'
    built = subprocess.run([compiler, 'build', source, '--ir', *flags, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    work = next(body for body in re.split(r'^fn ', built.stdout, flags=re.M)
                if body.startswith('f_work_'))
    # A non-leaf callee is too large for ordinary inlining. Specialization
    # removes the two literal-mode calls but keeps the dynamic-mode call.
    calls = re.findall(r'\bcall a=\d+ b=2 c=0 ', work)
    expected = 1 if flags == ['--release'] and not noinline else 3
    assert len(calls) == expected, work
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['-15', '17', '25', '27', '136']


@pytest.mark.core_quick
def test_new_expansion_stays_outside_loops(compiler, tmp_path):
    source = tmp_path / 'loop.jo'
    source.write_text(SOURCE.format(annotation='') + '''
@noinline
loop_work = () -> int:
    total = 0
    loop x in [0..4): total += choose(0, x)
    return total
print(loop_work())
''')
    binary = tmp_path / 'loop'
    built = subprocess.run([compiler, 'build', source, '--release', '--ir', '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    body = next(body for body in re.split(r'^fn ', built.stdout, flags=re.M)
                if body.startswith('f_loop_work_'))
    assert len(re.findall(r'\bcall a=\d+ b=2 c=0 ', body)) == 1, body
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines()[-1] == '34'
