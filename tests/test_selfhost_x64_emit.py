"""Whole x64 function emission: frozen bytes, COW, metadata and reused state."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
code: u8[]
data_fix: (int, int, int)[]
rodata: u8[]
ro_starts: int[]
uw_data: int[]
fused_on = false
notes: (int, int)[]
note_ro = (bits: int, off: int): notes.push((bits, off))
host = X64EmitHost(note_ro)
binding = x64_encoder_bind(&code, &data_fix)
emitter_binding = x64_emitter_bind(&rodata, &ro_starts, &uw_data, &fused_on, &host)
layouts = ir_operand_layouts()
positions = [0, 71, 71, 93]
cabi = fill(false, 32)

render = (f: IrFn) -> str:
    s = "{f.vtypes}:{f.args}:{f.kval}:{f.slot_size}:{f.slot_align}\n"
    loop i in f.code: s += "{i.op} {i.ty} {i.dst} {i.a} {i.b} {i.c} {i.imm} {i.pos}\n"
    s

run = (input: IrFn, debug: bool = false, windows: bool = false, fused: bool = false, priority: bool = false):
    before = render(input)
    ir = input
    code = fill(u8(0xCC), 16)
    saved = code
    rodata = [u8(1)]
    saved_ro = rodata
    ro_starts = []
    ro_consts = {}
    ro_new = []
    notes = []
    uw_data = []
    call_fix = []
    stub_fix = []
    cabi_fix = []
    data_fix = []
    line_rows = []
    call_sites = []
    rsp_rows = []
    ra_save_cost = 0
    ra_save_x = 0
    ra_stat = true
    backend_debug_vregs = [0, 1]
    backend_analyze(ir, layouts, debug, false, true, true)
    x64_allocate(&ir, priority, debug, true)
    rsp_frame = not debug and not windows
    x_padding_floor = code.len()
    x_padding_cmov = -1
    pad_moves = false
    fused_on = fused
    body = x64_emit(&ir, code.len(), debug, windows, fused, 33, -48, &cabi, &positions)
    assert(render(input) == before and render(ir) == before, "read-only IR")
    assert(saved == fill(u8(0xCC), 16) and saved_ro == [u8(1)], "output COW")
    print("body {body}; error {xe_emit_error}; lines {line_rows}; sites {call_sites}; row {row_pos}")
    print("call {call_fix}; stub {stub_fix}; cabi {cabi_fix}; data {data_fix}")
    print("frame {frame_size}; spills {vspill}; slots {slot_off}; saves {callee_off}; unwind {uw_data}")
    print("ro {rodata}; offsets {ro_starts}; new {ro_new}; notes {notes}; rsp {rsp_rows}")
    print("save {ra_save_cost} {ra_save_x}; padding {pad_moves}")
    if debug:
        loop i in [0..ir.code.len() + 1): print(dbg_pos[i])
        print(dbg_epis)
    print(code)

main = ():
    types = fill(i8(0), 16)
    types[4] = i8(1)
    types[5] = i8(2)
    types[12] = i8(3)
    f = IrFn(nparams=6, ret=0, vtypes=types, args=[i32(0), i32(1), i32(2), i32(3), i32(4), i32(5)], kval=fill(0, 13), slot_size=[i32(8), i32(16), i32(32), i32(4096)], slot_align=[i32(8), i32(16), i32(32), i32(64)], decl_pos=1)
    loop tag in [0..layouts.len()):
        loop ty in [0, 1, 2]:
            ins = Ins(Op(tag), ty=i32(ty), dst=6, a=0, b=2, c=1, imm=1, pos=2)
            if ins.op == .vop: ins.imm = 32 | VOP_SPLAT_B | VOP_SPLAT_C
            if ins.op == .load or ins.op == .store: ins.c = 8
            if ins.op == .br or ins.op == .brif or ins.op == .brtable: ins.imm = 0
            if ins.op == .brtable: ins.b = 1; ins.c = 0
            if ins.op == .zeroslots: ins.b = 1
            f.code = [ins, Ins(.ret, a=6, pos=3)]
            if ins.op == .loop or ins.op == .block or ins.op == .if_: f.code = [ins, Ins(.end), Ins(.ret, a=6)]
            if ins.op == .br or ins.op == .brif or ins.op == .brtable: f.code = [Ins(.block), ins, Ins(.end), Ins(.ret, a=6)]
            if ins.op == .end: f.code = [Ins(.block), ins, Ins(.ret, a=6)]
            if ins.op == .else_: f.code = [Ins(.if_, a=0), ins, Ins(.end), Ins(.ret, a=6)]
            run(f)
    loop op in [Op.load, Op.store]:
        loop size in [1, 2, 4, 8]:
            loop flags in [0, M_SIGNED, M_FLOAT, M_INDEX, M_SIGNED | M_INDEX, M_FLOAT | M_INDEX]:
                loop scale in [0, 1, 2, 3]:
                    loop off in [-257, -1, 0, 256, 32768]:
                        f.code = [Ins(op, dst=6, a=0, b=1, c=i32(size | flags | (scale << 8)), imm=off), Ins(.ret, a=6)]
                        run(f)
    loop op in [Op.call, Op.calli, Op.callc]:
        loop stub in [0..6):
            loop dst in [-1, 6]:
                loop debug in [false, true]:
                    loop windows in [false, true]:
                        f.code = [Ins(op, dst=i32(dst), a=0, b=6, c=i32(stub), imm=4, pos=2), Ins(.ret, a=i32(dst), pos=3)]
                        run(f, debug, windows, debug, not debug)
    loop value in [-9223372036854775807 - 1, -4097, -4096, -1, 0, 4095, 4096, 9223372036854775807]:
        f.code = [Ins(.iconst, dst=7, imm=value), Ins(.fconst, dst=4, imm=value), Ins(.fconst, dst=5, ty=2, imm=value), Ins(.fadd, dst=8, a=4, b=4, ty=1), Ins(.add, dst=6, a=0, b=7), Ins(.eq, dst=9, a=0, b=7), Ins(.if_, a=9), Ins(.checked_add, dst=6, a=6, b=7, imm=4), Ins(.end), Ins(.ret, a=6)]
        run(f, true)
    run(IrFn())
    run(IrFn(nparams=1, vtypes=[i8(0), i8(0)], code=[Ins(.mov, dst=1, a=0), Ins(.ret, a=1)]), true)
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_x64_emitter_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('ir_types', 'ir_operands', 'backend_analysis', 'x64_allocate', 'x64_encode', 'x64_emit')
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
        (directory / "output").write_bytes(ran.stdout)
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
