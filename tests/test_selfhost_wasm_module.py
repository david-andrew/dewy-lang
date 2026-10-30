"""Whole wasm modules and HTML assembly against frozen bytes and host events."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
files: SrcFile[] = [SrcFile(path="/root/é/main.dewy"), SrcFile(path="lib/other.dewy")]
positions: int[] = [0, 1, (1 << 40) | 8, (9 << 40) | 1]
reads: str[]
missing = ""
line = (id: int) -> int: id * 3
name = (s: str) -> str: s
read_js = (part: str) -> str:
    reads.push(part)
    if part == missing or part == "audio.js": return ""
    "// {part} é"
host = WasmModuleHost(&files, &positions, line, name, read_js)
binding = wm_bind(&host)

reset = (main_code: bool, signed: bool):
    type_sigs = []
    type_index = {}
    table_funcs = []
    table_index = {}
    wfuncs = []
    wf_present = []
    wm_abi = [WasmABI(imported=true, name="probe", params=[WT_I32, WT_I64, WT_I32], ret=WT_I32), WasmABI(), WasmABI(params=[WT_I32, WT_F64, WT_F32], ret=WT_I32, signed=[signed, false, false]), WasmABI()]
    wasm_user_pos = [false, true, true, false]
    f = IrFn(fn_index=1, name="f_main_123", nparams=0, ret=(if main_code: VI else: -1), vtypes=[i8(VI), i8(VI), i8(VI), i8(VI)], kval=[3, 4, 5, 0], args=[i32(0), i32(1), i32(2)], slot_size=[i32(17), i32(70001)], slot_align=[i32(8), i32(16)])
    f.code = [Ins(.iconst, dst=0, imm=3), Ins(.iconst, dst=1, imm=4), Ins(.iconst, dst=2, imm=5), Ins(.call, dst=3, a=0, b=3, imm=0, pos=1), Ins(.faddr, dst=0, imm=2), Ins(.ret, a=i32(if main_code: 3 else: -1))]
    wasm_collect_function(f)
    f = IrFn(fn_index=2, name="f_export_1", export_name="é_export", nparams=3, ret=VI, vtypes=[i8(VI), i8(VF), i8(VS)], kval=[0, 0, 0], code=[Ins(.ret, a=0)])
    wasm_collect_function(f)

main = ():
    loop main_code in [false, true]:
        loop signed in [false, true]:
            reset(main_code, signed)
            before = wfuncs
            present = wf_present
            ro: u8[] = [0xFF, 0x80, 0]
            image = wasm_image([], 1, main_code, 0, ro, 1234, 16)
            assert(wm_error == 0 and image[0] == 0 and image[1] == 'a' and image[2] == 's' and image[3] == 'm', "wasm magic")
            assert(wfuncs.len() == before.len() and wf_present == present and wfuncs[1].code.len() == before[1].code.len(), "readonly function collection")
            print(image)
            print(type_sigs)
            print(table_funcs)
            print("{stack_top}:{data_base}:{max_frame}")
    loop op in [Op.rot32, Op.overflow_add]:
        reset(false, false)
        wfuncs[1].code = [Ins(op, dst=0, a=1, b=2)]
        image = wasm_image([], 1, false, -1, [], 0, 0)
        assert(image.len() == 0 and wm_error != 0, "unsupported IR status")
        print("{wm_error}:{wm_error_lf}")
    reset(false, false)
    tbl(3)
    assert(wasm_image([], 1, false, -1, [], 0, 0).len() == 0 and wm_error == 3 and wm_error_lf == 3, "missing table target")
    reset(false, false)
    wfuncs = []
    wf_present = []
    wm_abi = []
    print(wasm_image([], -1, false, -1, [], 0, 0))
    # Custom source sections retain first-use file/name ordering and skip invalid files.
    out: u8[] = [42]
    before = out
    w_line_section(out, 100, [8, 32], [[4, 1, 8, 2, 12, 3], [4, 2]], ["é", "other"])
    assert(before == [u8(42)], "source-section COW")
    print(out)
    loop part in ["", "runtime.js", "gfx.js", "audio.js", "boot.js"]:
        missing = part
        loop with_icon in [false, true]:
            reads = []
            icon: u8[]
            if with_icon: icon = [0, 0x80, 0xFF]
            html = html_image([u8(0), u8(97), u8(115), u8(109)], "tïtle", icon, "// own JS")
            print(html)
            print("{html_missing}:{reads}")
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_wasm_module_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('ir_types', 'ir_operands', 'wasm_emit', 'leb128', 'base64', 'source_types', 'wasm_module')
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
