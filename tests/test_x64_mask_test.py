"""Mask tests preserve full-width bits, spilled operands and live AND results."""
import ctypes
import mmap
import platform
import subprocess

import pytest

from tests.support import ROOT, compiler

pytestmark = pytest.mark.skipif(
    platform.system() != 'Linux' or platform.machine() != 'x86_64',
    reason='executes Linux x86-64 machine code')


@pytest.mark.core_quick
def test_mask_flags_and_frames(compiler, tmp_path):
    source = tmp_path / 'mask_flags.jo'
    source.write_text(f"use '{ROOT / 'compiler/x64.jo'}'\nuse '{ROOT / 'compiler/backend_analysis.dewy'}'\n" + '''
vloc_storage = [RDI, RSI]
vloc = data(vloc_storage)
vcval_storage = [0, 0]
vcval = data(vcval_storage)
vspill = [-8, -16]
frame_size = 256
loop rsp in [false, true]:
    loop mode in [0..5):
        loop mask in [-9223372036854775807 - 1, -2147483648, -1, 0, 1, 127, 128, 2147483647, 2147483648, 4294967295, 9223372036854775807]:
            if mode < 3 and mask != 0: continue
            loop offset in [0, 19, 25, 31]:
                code = []
                rsp_frame = false
                rsp_extra = 0
                b(0x55); mov_rr(RBP, RSP)
                b(0x48); b(0x81); b(0xEC); b32(frame_size)
                mov_mr(RBP, -8, RDI)
                mov_mr(RBP, -16, RSI)
                vloc[0] = if mode == 1 or mode == 2 or mode == 4: LOC_SPILL else: RDI
                vloc[1] = if mode >= 3: LOC_CONST else if mode == 2: LOC_SPILL else: RSI
                vcval[1] = mask
                nop_pad(offset)
                rsp_frame = rsp
                x_test_ops(0, 1, true)
                b(0x9C); b(0x58); b(0xC9); b(0xC3)
                text = "{mode} {mask}"
                loop byte in code: text += " {int(byte)}"
                print(text)
''')
    binary = tmp_path / 'mask_flags'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    run = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    values = [-(1 << 63), -2147483649, -1, 0, 1, 128, 2147483648,
              4294967295, (1 << 63) - 1]
    with mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC) as page:
        address = ctypes.addressof(ctypes.c_char.from_buffer(page))
        call = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_int64, ctypes.c_int64)(address)
        for line in run.stdout.splitlines():
            mode, mask, *encoded = map(int, line.split())
            page.seek(0)
            page.write(bytes(encoded))
            for left in values:
                for right in ([mask] if mode >= 3 else values):
                    assert bool(call(left, right) & 64) == (left & right == 0)


@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']], ids=['default', 'release', 'debug'])
def test_mask_value_and_branch_consumers(compiler, tmp_path, flags):
    source = tmp_path / 'mask_consumers.jo'
    source.write_text('''
@noinline
is_zero = (a: int, b: int) -> bool: (a & b) == 0
@noinline
is_nonzero = (a: int, b: int) -> bool: (a & b) != 0
@noinline
classify = (a: int, b: int) -> int:
    if a & b != 0: return 100
    return 200
@noinline
check = (a: int, b: int) -> int:
    total = classify(a, b) + int(is_zero(a, b)) * 12 + int(is_nonzero(a, b)) * 24
    if a & b != 0: total += 1
    if 0 == (a & b): total += 2
    equal = (a & b) == 0
    different = (a & b) != 0
    total += int(equal) * 4 + int(different) * 8
    # Keep the mask live beyond its branch; it must not be replaced by flags.
    mask = a & b
    if mask != 0: total += mask & 255
    # A mutable result has another definition and observable later uses.
    mask = a | b
    total += mask & 15
    total
loop a in [-9223372036854775807 - 1, -2147483649, -1, 0, 1, 128, 2147483648, 9223372036854775807]:
    loop b in [-9223372036854775807 - 1, -2147483648, -1, 0, 1, 127, 2147483648, 4294967295]:
        print(check(a, b))
''')
    binary = tmp_path / 'mask_consumers'
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    run = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stdout + run.stderr
    expected = []
    for a in [-(1 << 63), -2147483649, -1, 0, 1, 128, 2147483648, (1 << 63) - 1]:
        for b in [-(1 << 63), -2147483648, -1, 0, 1, 127, 2147483648, 4294967295]:
            expected.append((133 + ((a & b) & 255) if a & b else 218) + ((a | b) & 15))
    assert list(map(int, run.stdout.split())) == expected
