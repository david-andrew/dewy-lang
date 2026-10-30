"""Native debug locations and backtrace tables against frozen bytes."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_dwarf_format import SETUP

DRIVER = SETUP.replace('dbg_raw: int[]\n', '').replace('dbg_cfi: int[]\n', '') + r"""
aggregate = (t: int) -> bool: t == 12
main = ():
    reset()
    f = IrFn(nparams=1, vtypes=fill(i8(0), 4), kval=fill(0, 4), code=fill(Ins(.nop), 4), dbg_locals=[1, 2, 3])
    layout = ir_operand_layouts()
    backend_analyze(f, layout, false, false, false)
    slot_off = [-64, -48]
    vspill = [-32, -24, -16, -8]
    dbg_pos = [4, 8, 12, 16, 20]
    regs = [0, 2, 1, 3, 7, 6, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15]
    loop flags in [0, LF_PARAM, LF_PARAM | LF_MUTPARAM, LF_CAPTURE, LF_ALIAS, LF_BYREF]:
        loop loc in [LOC_NONE, LOC_GLOBAL, LOC_CONST, LOC_FCONST, LOC_SLOT, LOC_SPILL, 0, 7, 16, 31]:
            loop last in [-1, 0, 3]:
                loop ty in [2, 12]:
                    locals = [Local(), Local(name=6, type=i32(ty), flags=i32(flags), offset=-1, vreg=1), Local(name=7, type=2, offset=1), Local(name=0, type=2, offset=-1, vreg=0)]
                    v_live[1].first = 1
                    v_live[1].last = last
                    vloc[1] = loc
                    vslot[1] = 0
                    vsoff[1] = 8
                    vcval[1] = -1025
                    f.vtypes[1] = i8(if last < 0: 2 else: 1)
                    dbg_raw = [123]
                    before = dbg_raw
                    native_debug_function(&f, 64, 0, 4, regs, 16, 17, 6, aggregate)
                    assert(before == [123], "debug output COW")
                    print(dbg_raw)
    reset()
    call_sites = [4, 1, 8, 2, 16, 3, 24, 4, 32, 0]
    files[0].path = "/root/é/main.dewy"
    files[1].path = "é.dewy"
    saved = call_sites
    print(x64_line_table())
    print(pe_backtrace_info())
    assert(call_sites == saved, "backtrace input unchanged")
    rsp_rows = [0, 16, 128, -8, 4294967295, 32]
    print(x64_frame_table())
    call_sites = []
    print(x64_line_table())
    loop value in [-1, 0, 127, 128, 16383, 16384, 9223372036854775807]:
        out: u8[] = [0xAA]
        old = out
        put_varint(out, value)
        assert(old == [u8(0xAA)], "varint COW")
        print(out)
    loop name in ["", "plain", "f_", "f_x", "f_é_123", "f_é_xyz", "f__123", "f_ä_", "f_é_１２"]: print(sym_name(name))
    print("ok")
"""


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_native_debug_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_state', 'source_types', 'elf_format', 'leb128', 'module_paths', 'json_doc', 'dwarf_format', 'ir_types', 'ir_operands', 'backend_analysis', 'x64_allocate', 'x64_encode', 'x64_emit', 'native_debug')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
