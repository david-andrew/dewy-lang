"""Representation boundary checks against Python integers, plus the scalar ABI."""
import subprocess

import pytest

from tests.test_core import compiler
from tests.test_int_semantics import int_program, run


@pytest.mark.parametrize('op,x,y', [
    ('add', (1 << 62) - 1, 1), ('sub', -(1 << 62), 1),
    ('add', -(1 << 62), -1), ('sub', (1 << 62) - 1, -1),
    ('mul', -(1 << 62), -1), ('mul', (1 << 62) - 1, 2),
    ('mul', -(1 << 61), 2), ('mul', -(1 << 61) - 1, 2),
    ('div', -(1 << 62), -1), ('mod', -(1 << 62), -1),
    ('div', -(1 << 62) - 1, 3), ('mod', -(1 << 62) - 1, 3),
    ('shl', (1 << 61) - 1, 1), ('shl', 1 << 61, 1),
    ('shr', -(1 << 62), 63), ('shr', (1 << 62) - 1, 63),
    ('neg', -(1 << 62), 0), ('neg', (1 << 62) - 1, 0),
    ('parse', str(1 << 62), 0), ('parse', str(-(1 << 62) - 1), 0),
])
def test_small_integer_boundary(int_program, op, x, y):
    expected = {
        'add': lambda: x + y, 'sub': lambda: x - y, 'mul': lambda: x * y,
        'div': lambda: x // y, 'mod': lambda: x % y,
        'shl': lambda: x << y, 'shr': lambda: x >> y,
        'neg': lambda: -x, 'parse': lambda: int(x),
    }[op]()
    result = run(int_program, op, x, y)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(expected)


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_tagged_integer_layout(compiler, tmp_path, release):
    source = tmp_path / 'layout.jo'
    source.write_text('''type OptionalInt = __dewy_int?
main = () -> int:
    if size_of(__dewy_int) != 8: return 1
    if size_of(OptionalInt) != 8: return 2
    values: __dewy_int[] = [1, 2]
    if ((data(values) + 1) as int) - (data(values) as int) != 8: return 3
    0
''')
    binary = tmp_path / 'layout'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    result = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
