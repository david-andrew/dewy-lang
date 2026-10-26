"""Spill comparisons preserve flags across immediate widths and frame layouts."""
import ctypes
import mmap
import platform
import subprocess

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
@pytest.mark.skipif(platform.system() != 'Linux' or platform.machine() != 'x86_64',
                    reason='executes Linux x86-64 machine code')
def test_spill_compare_flags(compiler, tmp_path):
    source = tmp_path / 'spill_compare.jo'
    source.write_text(f"use '{ROOT / 'compiler/x64.jo'}'\n" + '''
vloc_storage = [LOC_SPILL, LOC_CONST]
vloc = data(vloc_storage)
vcval_storage = [0, 0]
vcval = data(vcval_storage)
vspill = [-8, 0]
frame_size = 1024
loop rsp in [false, true]:
    loop extra in [0, 16]:
        loop displacement in [-8, -128, -136, -1024]:
            loop mode in [-1, RSI, R8, R9]:
                loop value in [-2147483648, -129, -128, -1, 0, 127, 128, 2147483647]:
                    if mode >= 0 and value != 0: continue
                    loop branch in [false, true]:
                        loop offset in [0, 19, 25, 31]:
                            code = []
                            rsp_frame = false
                            b(0x55); mov_rr(RBP, RSP)
                            b(0x48); b(0x81); b(0xEC); b32(frame_size + extra)
                            mov_mr(RBP, displacement, RDI)
                            if mode >= 0 and mode != RSI: mov_rr(mode, RSI)
                            nop_pad(offset)
                            rsp_frame = rsp
                            rsp_extra = extra
                            vspill[0] = displacement
                            vloc[1] = if mode < 0: LOC_CONST else: mode
                            vcval[1] = value
                            start = code.len()
                            cmp_ops(0, 1, branch)
                            finish = code.len()
                            # Return the flags unchanged, including CF, ZF, SF and OF.
                            b(0x9C); b(0x58); b(0xC9); b(0xC3)
                            text = "{mode} {value} {start} {finish} {branch}"
                            loop byte in code: text += " {int(byte)}"
                            print(text)
''')
    binary = tmp_path / 'spill_compare'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    mask = (1 << 64) - 1
    values = [-(1 << 63), -2147483649, -129, -128, -1, 0, 127, 128,
              2147483648, (1 << 63) - 1]
    with mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC) as page:
        address = ctypes.addressof(ctypes.c_char.from_buffer(page))
        call = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_int64, ctypes.c_int64)(address)
        for line in ran.stdout.splitlines():
            mode, constant, start, finish, branch, *encoded = line.split()
            mode, constant, start, finish = map(int, (mode, constant, start, finish))
            code = bytes(map(int, encoded))
            if branch == 'false':
                # One CMP with a memory ModRM, without an intervening load.
                assert code[start] & 0xF8 == 0x48
                assert code[start + 1] in (0x39, 0x81, 0x83)
                assert code[start + 2] & 0xC0 != 0xC0
                assert finish - start <= 12
            page.seek(0)
            page.write(code)
            for left in values:
                for right in ([constant] if mode < 0 else values):
                    flags = call(left, right)
                    carry = bool(flags & 1)
                    zero = bool(flags & (1 << 6))
                    sign = bool(flags & (1 << 7))
                    overflow = bool(flags & (1 << 11))
                    assert zero == (left == right)
                    assert carry == ((left & mask) < (right & mask))
                    assert (sign != overflow) == (left < right)
