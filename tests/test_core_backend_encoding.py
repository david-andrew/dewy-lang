"""Direct byte reservations and bounded mixed-class argument moves."""
import os
import subprocess

import pytest

from tests.support import ROOT, compiler


def run_source(compiler, tmp_path, text, flags=()):
    source = tmp_path / 'encoding.jo'
    source.write_text(text)
    binary = tmp_path / 'encoding'
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           env={**os.environ, 'DEWY_EMIT_WORKERS': '1'},
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout


def test_encoding_reservations_preserve_shared_buffers(compiler, tmp_path):
    # Invoke the actual emitter with empty, shared and growing buffers. The
    # expected bytes are independent of the emitter's reserve/store strategy.
    source = f"use '{ROOT / 'compiler/x64.jo'}'\n" + '''
code = []
b16(0x1234)
original = code
b24(0x56789A)
b32(0xFEDCBA98)
b64(-2)
assert(original.len() == 2, "encoding")
assert(original[0] == 0x34 and original[1] == 0x12, "encoding")
expected: u8[] = [0x34, 0x12, 0x9A, 0x78, 0x56, 0x98, 0xBA, 0xDC, 0xFE,
                  0xFE, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
assert(code == expected, "encoding")
loop i in [0..4096):
    b32(i)
loop i in [0..4096):
    loop j in [0..4):
        assert(code[17 + 4 * i + j] == u8((i >> (8 * j)) & 255), "encoding")
assert(original == [u8(0x34), u8(0x12)], "encoding")
print("ok")
'''
    assert run_source(compiler, tmp_path, source) == 'ok\n'


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_mixed_register_cycles_and_stack_arguments(compiler, tmp_path, flags):
    # Both classes exceed their ABI registers. Reversing the parameters makes
    # register cycles and reversed stack spans observable in a weighted sum.
    ints, floats = 10, 12
    params = [f'i{k}: int' for k in range(ints)] + [f'f{k}: f64' for k in range(floats)]
    expr = ' + '.join([f'i{k} * {k + 1}' for k in range(ints)] +
                      [f'int(f{k} * {k + 11}.0)' for k in range(floats)])
    args = [f'i{k}' for k in reversed(range(ints))] + [f'f{k}' for k in reversed(range(floats))]
    source = '@noinline\nsum = (' + ', '.join(params) + ') -> int:\n    ' + expr + '\n'
    source += '@noinline\nreverse = (' + ', '.join(params) + ') -> int:\n'
    source += '    sum(' + ', '.join(args) + ')\n'
    values = [str(k + 3) for k in range(ints)] + [f'{k + 7}.0' for k in range(floats)]
    source += 'print(reverse(' + ', '.join(values) + '))\n'
    expected = sum((ints - 1 - k + 3) * (k + 1) for k in range(ints))
    expected += sum((floats - 1 - k + 7) * (k + 11) for k in range(floats))
    assert run_source(compiler, tmp_path, source, flags).strip() == str(expected)
