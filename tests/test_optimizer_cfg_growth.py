"""Strength-reduction growth must preserve the shared structured CFG."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_optimizer_cfg_after_output_growth(compiler, tmp_path, release):
    divisors = [k for k in range(3, 93) if k & (k - 1)]
    source = tmp_path / 'cfg-growth.jo'
    lines = ['work = (n: int) -> int:', '    total = 0']
    lines += [f'    total += n / {k}' for k in divisors]
    lines += [
        '    if n == 0:',
        '        return -1',
        '        loop i in [0..3): total += i',
        '    else:',
        '        if n < 0:',
        '            return -2',
        '            total += 77',
        '    loop i in [0..3):',
        '        if i == 2: break',
        '        total += i',
        '    return total',
        'print(work(1000003))',
        'print(work(0))',
        'print(work(-1))',
    ]
    source.write_text('\n'.join(lines) + '\n')
    binary = tmp_path / 'cfg-growth'
    result = subprocess.run([compiler, 'build', source, '-o', binary,
                             *(['--release'] if release else [])],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == f'{sum(1000003 // k for k in divisors) + 1}\n-1\n-2\n'
