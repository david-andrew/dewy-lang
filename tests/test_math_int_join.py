"""Peeling an explicit int conversion must preserve validity and exact values."""
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

DATA = Path(__file__).parent / 'fixtures/math_int_join'
A, B = -(2**63), 2**64 - 1
SIGNED = 2**63 - 1
EXPECTED = {
    'mixed_math_add': '1\n',
    'mixed_math_subtract': '-3\n',
    'mixed_math_multiply': '-2\n',
    'mix_cast_left': f'{A*B}\n',
    'mix_cast_both': f'{A*B}\n',
    'mix_cast_right': f'{A*B}\n',
    'mixed_math_add_control': '1\n',
    'mixed_math_subtract_control': '-3\n',
    'mixed_math_multiply_control': '-2\n',
    'mixed_math_calls': '-2\n1\n9\n',
    'mixed_math_edges': '\n'.join(map(str, [A+B, B+A, A-B, B-A, A*B, B*A])) + '\ntrue\n18446744073709551616\n',
    'signed_exact_control': '\n'.join(map(str, [SIGNED*2, 0, SIGNED**2, SIGNED+2**32-1])) + '\n',
}


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('name', EXPECTED)
def test_math_int_join(compiler, tmp_path, release, name):
    binary = tmp_path / 'out'
    built = subprocess.run([compiler, 'build', DATA / f'{name}.dewy', '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == EXPECTED[name]
