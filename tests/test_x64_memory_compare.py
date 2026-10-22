"""Integer memory comparisons preserve extensions, ordering and failure paths."""
import os
import platform
import re
import shutil
import subprocess

import pytest

from tests.support import compiler


def build(compiler, tmp_path, source, flags):
    path = tmp_path / 'memory_compare.jo'
    path.write_text(source)
    binary = tmp_path / 'memory_compare'
    result = subprocess.run([compiler, 'build', path, '-o', binary, *flags],
                            capture_output=True, text=True, timeout=60,
                            env={**os.environ, 'SLOPPY_EMIT_WORKERS': '1'})
    assert result.returncode == 0, result.stdout + result.stderr
    return binary


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_memory_compare_widths_and_order(compiler, tmp_path, flags):
    definitions, checks = [], []
    for ty, values, constants in [
        ('i8', [-128, -1, 0, 127], [-129, -128, -1, 0, 127, 128, 255]),
        ('u8', [0, 127, 128, 255], [-1, 0, 127, 128, 255, 256]),
        ('i16', [-32768, -1, 0, 32767], [-32769, -32768, -1, 0, 32767, 32768]),
        ('u16', [0, 32768, 65535], [-1, 0, 32768, 65535, 65536]),
        ('i32', [-2147483648, -1, 2147483647], [-2147483649, -1, 0, 2147483647, 2147483648]),
        ('u32', [0, 2147483648, 4294967295], [-1, 0, 2147483648, 4294967295]),
        ('int', [-9223372036854775807, -1, 0, 9223372036854775807], [-1, 0, 127, 128]),
    ]:
        for index, constant in enumerate(constants):
            for op, label in [('==', 'eq'), ('!=', 'ne'), ('<', 'lt'), ('>', 'gt')]:
                name = f'probe_{ty}_{index}_{label}'
                definitions.append(f'@noinline\n{name} = (xs: {ty}[], i: int) -> bool: int(xs[i]) {op} {constant}\n')
                for value in values:
                    expected = eval(f'{value} {op} {constant}')
                    checks.append(f'assert({name}([{ty}({value})], 0) == {str(expected).lower()}, "{name}: {value}")')
    definitions.append('''@noinline
ordered = (xs: int[], i: int, value: int) -> int:
    if xs[i] < value: return 1
    if value < xs[i]: return 2
    3
@noinline
selected = (xs: int[], i: int, value: int) -> int:
    if xs[i] == value: 17 else: 29
''')
    checks += ['assert(ordered([2], 0, 3) == 1)', 'assert(ordered([3], 0, 2) == 2)',
               'assert(ordered([3], 0, 3) == 3)', 'assert(selected([3], 0, 3) == 17)',
               'assert(selected([3], 0, 2) == 29)', 'print("ok")']
    binary = build(compiler, tmp_path, '\n'.join(definitions + checks), flags)
    result = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and result.stdout == 'ok\n', result.stdout + result.stderr
    if not flags or flags == ['--release']:
        if platform.machine().lower() in ('x86_64', 'amd64') and shutil.which('objdump'):
            assembly = subprocess.check_output(['objdump', '-d', '-Mintel', '--disassemble=selected', binary], text=True)
            assert re.search(r'cmp\s+[^\n]*QWORD PTR', assembly), assembly


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.parametrize('index', [-1, 1])
def test_memory_compare_keeps_bounds_failure(compiler, tmp_path, flags, index):
    binary = build(compiler, tmp_path, f'''@noinline
probe = (xs: int[], i: int) -> bool: xs[i] == 3
print(probe([3], {index}))
''', flags)
    result = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'bounds' in result.stderr, result.stderr
