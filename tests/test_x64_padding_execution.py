"""Execute boundary fixups: prefixes must preserve registers, flags and targets."""
import ctypes
import mmap
import platform
import subprocess

import pytest
from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.skipif(platform.system() != 'Linux' or platform.machine() != 'x86_64',
                    reason='executes Linux x86-64 machine code')
def test_padding_preserves_execution(compiler, tmp_path):
    source = tmp_path / 'padding.jo'
    source.write_text(f"use '{ROOT / 'compiler/x64.jo'}'\nuse '{ROOT / 'compiler/ir.jo'}'\n" + '''
fragments = [
    [0x48, 0xB8, 7, 0, 0, 0, 0, 0, 0, 0],
    [0x48, 0x89, 0xF8],
    [0x48, 0x8D, 0x47, 2],
    [0x48, 0x83, 0xC0, 7],
    [0x48, 0x81, 0xC0, 7, 0, 0, 0],
    [0x48, 0xC7, 0xC0, 7, 0, 0, 0],
    [0x48, 0x01, 0xF8],
    [0x48, 0x31, 0xF8]
]
loop index in [0..fragments.len()):
    loop offset in [6..96):
        code = []
        b(0x31); b(0xC0) # xor eax,eax
        b(0x48); b(0x83); b(0xFF); b(0) # cmp rdi,0
        loop k in [6..offset): b(0x90)
        fix = jcc32(CC_E)
        loop byte in fragments[index]: b(byte)
        b(0xC3)
        target = code.len()
        b(0xB8); b32(11); b(0xC3)
        patch_branch(fix, target)
        text = "{index}"
        loop byte in code: text += " {int(byte)}"
        print(text)
vloc_storage = [RAX, LOC_CONST, LOC_CONST]
vloc = data(vloc_storage)
vcval_storage = [0, 0x1234, 0]
vcval = data(vcval_storage)
loop blocks in [0..9):
    loop padding in [1..9):
        code = []
        b(0x48); b(0x89); b(0xF8) # mov rax,rdi
        b(0x48); b(0x81); b(0xE0); b32(0x1234) # and rax,0x1234
        original = code
        ir.code = [Ins(.and_, 0, 0, 0, 1, 0, 0)]
        loop k in [0..blocks): ir.code.push(Ins(.block, 0, -1, 0, 0, 0, 0))
        ir.code.push(Ins(.eq, 0, 2, 0, 2, 0, 0))
        x_branch_pos = ir.code.len()
        ir.code.push(Ins(.brif, 0, -1, 2, 0, 0, 0))
        assert(x_absorb_padding(padding), "padding not absorbed")
        assert(original.len() == 10 and original[3] == 0x48, "shared bytes changed")
        b(0xC3)
        text = "8"
        loop byte in code: text += " {int(byte)}"
        print(text)
vcval_storage[1] = 1
vcval = data(vcval_storage)
loop blocks in [0..9):
    loop padding in [1..12):
        code = []
        b(0x48); b(0x89); b(0xF8)
        b(0x48); b(0x83); b(0xE8); b(1) # sub rax,1
        original = code
        ir.code = [Ins(.sub, 0, 0, 0, 1, 0, 0)]
        loop k in [0..blocks): ir.code.push(Ins(.end, 0, -1, 0, 0, 0, 0))
        ir.code.push(Ins(.eq, 0, 2, 0, 2, 0, 0))
        x_branch_pos = ir.code.len()
        ir.code.push(Ins(.brif, 0, -1, 2, 0, 0, 0))
        x_padding_floor = code.len()
        assert(not x_absorb_padding(padding), "moved a branch destination")
        assert(code == original, "rejected padding changed bytes")
        x_padding_floor = 3
        assert(x_absorb_padding(padding), "narrow padding not absorbed")
        assert(original.len() == 7 and original[3] == 0x48, "shared bytes changed")
        b(0xC3)
        text = "9"
        loop byte in code: text += " {int(byte)}"
        print(text)
''')
    binary = tmp_path / 'padding'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    for line in ran.stdout.splitlines():
        index, *values = map(int, line.split())
        with mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC) as page:
            page.write(bytes(values))
            address = ctypes.addressof(ctypes.c_char.from_buffer(page))
            call = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64)(address)
            assert call(0) == (0 if index == 8 else -1 if index == 9 else 11)
            assert call(5) == [7, 5, 7, 7, 7, 7, 5, 5, 4, 4][index]
