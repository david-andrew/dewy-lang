"""X64 module emission: entry/adapter/stub bytes, relocation order and COW."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
code: u8[]
data_fix: (int, int, int)[]
binding = x64_encoder_bind(&code, &data_fix)
reset = ():
    code = []
    data_fix = []
    call_fix = []
    cabi_fix = []
    stub_fix = []
    cabi_adapter = {}
    stub_addr = fill(-1, 13)
    line_rows = []
    rsp_rows = []
    rsp_frame = false
    rsp_extra = 0
    row_pos = -1

show = ():
    print(code)
    print(data_fix)
    print(call_fix)
    print(line_rows)
    print(rsp_rows)
    print(row_pos)

main = ():
    loop frames in [false, true]:
        loop padding in [0, 1, 15, 16]:
            reset()
            if frames: rsp_rows = [0, 8]
            code = fill(u8(0xCC), padding)
            saved = code
            before = stub_addr
            x64_emit_stubs()
            assert(saved == fill(u8(0xCC), padding) and before == fill(-1, 13), "stub COW")
            loop i in [2..13):
                if i == 10: assert(stub_addr[i] == -1, "unassigned stub")
                else: assert(stub_addr[i] >= padding and stub_addr[i] % 16 == 0, "stub alignment")
            print(stub_addr)
            show()
    loop windows in [false, true]:
        loop watch in [false, true]:
            loop main_lf in [-1, 0, 7]:
                loop end_lf in [-1, 8]:
                    loop main_code in [false, true]:
                        reset()
                        code = [u8(0xCC)]
                        saved = code
                        rsp_rows = [0, 8]
                        inits = [2, 3, 4]
                        before = inits
                        start = 0
                        if windows: start = x64_emit_entry_win(inits, main_lf, main_code, end_lf, watch, 0x50000000, 0x20000000, -64)
                        else: start = x64_emit_entry(inits, main_lf, main_code, end_lf, watch, 0x50000000, 0x20000000)
                        assert(start == 16 and saved == [u8(0xCC)] and inits == before, "entry snapshots")
                        expected = inits
                        if main_lf >= 0: expected.push(main_lf)
                        if end_lf >= 0: expected.push(end_lf)
                        assert(call_fix.len() == expected.len(), "call count")
                        loop i in [0..expected.len()): assert(call_fix[i].1 == expected[i], "initializer/main/flush order")
                        show()
    # All valid integer/float argument counts, including incoming stack arguments.
    loop ni in [0..7):
        loop nf in [0..9):
            reset()
            code = [u8(0xCC)]
            saved = code
            ptypes = fill(1, nf)
            loop i in [0..ni): ptypes.push(0)
            before = ptypes
            start = x64_emit_adapter(3, ptypes)
            assert(start == 16 and cabi_adapter[3] == start, "adapter address")
            assert(saved == [u8(0xCC)] and ptypes == before, "adapter snapshots")
            show()
    loop target in [0, 4, 4092, 4096, 0x100000]:
        loop base in [0, 4095, 0x100000000]:
            reset()
            code = fill(u8(0xAA), 24)
            saved = code
            cabi_fix = [(0, 1)]
            cabi_adapter[1] = target + 16
            stub_fix = [(4, 2)]
            stub_addr[2] = target + 32
            call_fix = [(8, 0)]
            data_fix = [(12, 0, 4097), (16, 1, -1)]
            functions = [target]
            before = functions
            assert(x64_patch_module(base, base + 0x10000, base + 0x20000, functions) == (0, -1), "resolved")
            assert(functions == before and saved == fill(u8(0xAA), 24), "relocation COW")
            print(code)
    # Error order and partial mutation are part of the original patching contract.
    reset()
    code = fill(u8(0xAA), 24)
    saved = code
    functions = [-1, -1]
    stub_fix = [(4, 2)]
    cabi_fix = [(0, 1)]
    call_fix = [(8, 1), (12, 0)]
    assert(x64_patch_module(0, 0, 0, functions) == (1, -1) and code == saved, "missing stubs first")
    stub_addr[2] = 16
    assert(x64_patch_module(0, 0, 0, functions) == (2, 1) and code == saved, "missing adapter second")
    cabi_adapter[1] = 32
    assert(x64_patch_module(0, 0, 0, functions) == (3, 1), "first unresolved call")
    assert(code != saved and code[8] == 0xAA and saved == fill(u8(0xAA), 24), "earlier patches retained")
    print(code)
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_x64_module_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('ir_types', 'ir_operands', 'backend_analysis', 'x64_allocate', 'x64_encode', 'x64_emit', 'x64_module')
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
