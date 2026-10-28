"""Native encoding twins: COW bytes, address forms, vector fields and branch slots."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
code: u8[]
fixups: (int, int, int)[]
binding = x64_encoder_bind(&code, &fixups)
reset = ():
    code = []
    fixups = []
    cur_index = -1
    cur_scale = 0
    rip_kind = 0
    rsp_frame = false
    rsp_extra = 0
    frame_size = 0

main = ():
    loop v in [-9223372036854775807 - 1, -2147483649, -2147483648, -129, -1, 0, 127, 128, 255, 65535, 2147483647, 2147483648, 9223372036854775807]:
        loop prefix in [0, 1, 7, 64]:
            reset()
            code = fill(u8(19), prefix)
            before = code
            b(v)
            b16(v)
            b24(v)
            b32(v)
            b64(v)
            assert(code.len() == prefix + 18 and before == fill(u8(19), prefix), "reservation/COW")
            saved = code
            patch32(prefix + 1, v)
            assert(saved.len() == code.len(), "patch keeps length")
            print(code)
            print(saved)
    reset()
    mov_rr(RAX, RCX)
    assert(code == [u8(0x48), u8(0x89), u8(0xC8)], "mov rax, rcx")
    # Prefix, scalar size and every addressing form, including RBP-to-RSP frames.
    loop framed in [false, true]:
        loop reg in [0..16):
            loop base in [0, 4, 5, 8, 12, 13, RIPREL]:
                loop disp in [-2147483648, -129, -128, 0, 127, 128, 2147483647]:
                    reset()
                    rsp_frame = framed
                    rsp_extra = 16
                    frame_size = 64
                    mov_rm(reg, base, disp)
                    mov_mr(base, disp, reg)
                    lea(reg, base, disp)
                    loop size in [1, 2, 4, 8]:
                        load_sized(reg, base, disp, size, true)
                        load_sized(reg, base, disp, size, false)
                        store_sized(base, disp, reg, size)
                    sse_rm(0xF2, 0x10, reg, base, disp)
                    print(code)
                    print(fixups)
    loop reg in [0..16):
        loop index in [-1, 0, 4, 8, 15]:
            loop scale in [0..4):
                reset()
                use_index(index, scale)
                rex(true, reg, index, 13, false)
                mem(reg, 13, -128)
                vmov_rm(reg, 4, 127, VX)
                vmov_mr(12, 128, reg, VY)
                vmov_rr(reg, 15 - reg, VY)
                sse_rr(0x66, 0x58, reg, 15 - reg)
                setcc_reg(reg & 15, reg)
                print(code)
    # All slot alignments, short/near limits and suffix fusion candidates.
    loop prefix in [0..32):
        loop distance in [-4096, -129, -128, -127, -1, 0, 1, 126, 127, 128, 4096]:
            loop condition in [-1, 0, 5, 15]:
                reset()
                code = fill(u8(0x90), prefix)
                pos = if condition < 0: jmp32() else: jcc32(condition)
                mov_rr(RAX, RCX)
                saved = code
                patch_branch(pos, pos + distance)
                assert(code.len() == saved.len(), "fixed branch slot")
                print(code)
                print(saved)
    loop n in [0..66):
        reset()
        nop_pad(n)
        assert(code.len() == n, "NOP length")
        print(code)
    reset()
    loop r in [0..16):
        loop v in [-2147483649, -2147483648, -1, 0, 2147483647, 2147483648]: mov_imm(r, v)
    rel_fixup_lea(15, 1, -17)
    print(code)
    print(fixups)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_x64_encoding_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        leaf = f'x64_encode.{extension}'
        (directory / leaf).write_text((ROOT / 'compiler' / leaf).read_text())
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use '{leaf}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=45)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
