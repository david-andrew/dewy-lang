"""Arm64 module emission: entry policies, stubs, relocations and rejection state."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
code: u8[]
binding = arm64_encoder_bind(&code)
reset = ():
    code = []
    a_call_fix = []
    a_stub_fix = []
    a_faddr_fix = []
    a_data_fix = []

main = ():
    # All stub entries and the preserved register-pair order, on reused storage.
    loop padding in [0, 4, 16]:
        reset()
        code = fill(u8(0), padding)
        stubs = fill(-1, 13)
        before_stubs = stubs
        before_code = code
        arm64_emit_stubs(stubs)
        assert(before_stubs == fill(-1, 13) and before_code.len() == padding, "stub snapshots")
        loop i in [2..13):
            if i == 10: assert(stubs[i] == -1, "unassigned stub")
            else: assert(stubs[i] >= padding and stubs[i] % 4 == 0, "aligned stub")
        assert(rd32(stubs[2]) == 0xA9005013, "setjmp saves x19/x20 first")
        assert(rd32(stubs[8]) == 0x910003E0, "stack pointer stub")
        print(stubs)
        print(code)
    # Linux entry/watch reservation and macOS return-to-dyld, all optional calls.
    loop mac in [false, true]:
        loop watch in [false, true]:
            loop main_lf in [-1, 0, 7]:
                loop end_lf in [-1, 8]:
                    loop main_code in [false, true]:
                        reset()
                        w32(0xD503201F)
                        inits = [2, 3, 4]
                        start = 0
                        if mac: start = arm64_emit_entry_mac(inits, main_lf, main_code, end_lf)
                        else: start = arm64_emit_entry(inits, main_lf, main_code, end_lf, watch, 0x600000000000, 0x10000000)
                        assert(start == 4 and a_data_fix == [(8 + (if mac: 12 else: 0), 1, 0)], "entry/data sites")
                        expected = inits
                        if main_lf >= 0: expected.push(main_lf)
                        if end_lf >= 0: expected.push(end_lf)
                        assert(a_call_fix.len() == expected.len(), "optional calls")
                        loop i in [0..expected.len()): assert(a_call_fix[i].1 == expected[i], "initializer/main/flush order")
                        print(code)
                        print(a_call_fix)
                        print(a_data_fix)
    # Resolve backward/forward branches and page-relative function/data addresses.
    loop target in [0, 4, 4092, 4096, 0x100000]:
        loop base in [0, 4095, 0x100000000]:
            reset()
            a_call_fix.push((code.len(), 0))
            a_bl()
            a_stub_fix.push((code.len(), 2))
            a_bl()
            a_faddr_fix.push((code.len(), 1))
            w32(0x90000011)
            w32(0x91000231)
            a_adr_data(9, 0, 4097)
            a_adr_data(10, 1, -1)
            before = code
            functions = [target, target + 8]
            stubs = [0, 0, target + 16]
            assert(arm64_patch_module(base, base + 0x10000, base + 0x20000, functions, stubs) == -1, "resolved")
            assert(before[0] == 0 and before[3] == 0x94, "relocation COW")
            assert(rd32(0) == (0x94000000 | ((target / 4) & 0x3FFFFFF)), "call displacement")
            print(code)
    # A missing first target must be reported before any patch; first missing wins.
    reset()
    a_call_fix = [(0, 1), (4, 0)]
    a_bl()
    a_bl()
    before = code
    functions = [-1, -1]
    stubs = fill(0, 13)
    assert(arm64_patch_module(0, 0, 0, functions, stubs) == 1 and code == before, "first unresolved call")
    a_call_fix = []
    a_faddr_fix = [(0, 0)]
    assert(arm64_patch_module(0, 0, 0, functions, stubs) == 0 and code == before, "unresolved address")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_arm64_module_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('ir_types', 'ir_operands', 'backend_analysis', 'arm64_allocate', 'arm64_encode', 'arm64_emit', 'arm64_module')
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
        ran = subprocess.run([binary], capture_output=True, timeout=30)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
