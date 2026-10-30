"""Arm64 function emitter: complete bytes, relocations, debug rows and errors."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
code: u8[]
binding = arm64_encoder_bind(&code)
layouts = ir_operand_layouts()
positions = [0, 71, 71, 93]

render = (f: IrFn) -> str:
    s = "{f.vtypes}:{f.args}:{f.kval}:{f.slot_size}:{f.slot_align}\n"
    loop i in f.code: s += "{i.op} {i.ty} {i.dst} {i.a} {i.b} {i.c} {i.imm} {i.pos}\n"
    s

run = (input: IrFn, debug: bool = false, mac: bool = false, fused: bool = false):
    before = render(input)
    ir = input
    code = [u8(1), u8(2), u8(3), u8(4), u8(5), u8(6), u8(7), u8(8)]
    saved = code
    a_call_fix = []
    a_stub_fix = []
    a_faddr_fix = []
    a_data_fix = []
    backend_debug_vregs = [0, 1]
    body = arm64_emit(&ir, layouts, positions, fused, debug, mac, false, 33, "unit")
    assert(render(input) == before and render(ir) == before, "read-only IR")
    assert(saved == [u8(1), u8(2), u8(3), u8(4), u8(5), u8(6), u8(7), u8(8)], "code COW")
    print("body {body}; error {a_emit_error}; lines {a_emit_lines}; sites {a_emit_sites}; row {a_row_pos}")
    print("call {a_call_fix}; stub {a_stub_fix}; function {a_faddr_fix}; data {a_data_fix}")
    print("frame {a_frame_size}; spills {a_spill}; slots {a_slots}; saves {a_saved}")
    if debug:
        loop i in [0..ir.code.len() + 1): print(a_positions[i])
        print(a_epis)
    # Literal pools are appended after the host consumes the debug end position.
    a_put_lits()
    print(code)
    assert(a_lits.len() == 0, "literal lifetime")

main = ():
    types = fill(i8(0), 16)
    types[4] = i8(1)
    types[5] = i8(2)
    types[12] = i8(3)
    f = IrFn(nparams=6, ret=0, vtypes=types, args=[i32(0), i32(1), i32(2), i32(3), i32(4), i32(5)], kval=fill(0, 13), slot_size=[i32(8), i32(16), i32(32), i32(4096)], slot_align=[i32(8), i32(16), i32(32), i32(64)], decl_pos=1)
    # Every opcode, supported or diagnosed, with scalar types and control shapes.
    loop tag in [0..layouts.len()):
        loop ty in [0, 1, 2]:
            ins = Ins(Op(tag), ty=i32(ty), dst=6, a=0, b=2, c=1, imm=1, pos=2)
            if ins.op == .vop: ins.imm = 32 | VOP_SPLAT_B | VOP_SPLAT_C
            if ins.op == .load or ins.op == .store: ins.c = 8
            if ins.op == .br or ins.op == .brif or ins.op == .brtable: ins.imm = 0
            if ins.op == .brtable: ins.b = 1; ins.c = 0
            f.code = [ins, Ins(.ret, a=6, pos=3)]
            if ins.op == .loop or ins.op == .block or ins.op == .if_: f.code = [ins, Ins(.end), Ins(.ret, a=6)]
            if ins.op == .end or ins.op == .br or ins.op == .brif or ins.op == .brtable: f.code = [Ins(.block), ins, Ins(.end), Ins(.ret, a=6)]
            if ins.op == .end: f.code = [Ins(.block), ins, Ins(.ret, a=6)]
            if ins.op == .else_: f.code = [Ins(.if_, a=0), ins, Ins(.end), Ins(.ret, a=6)]
            run(f)
    # Address modes include indexing, signed widths, large/negative displacements.
    loop op in [Op.load, Op.store]:
        loop size in [1, 2, 4, 8]:
            loop flags in [0, M_SIGNED, M_FLOAT, M_INDEX, M_SIGNED | M_INDEX, M_FLOAT | M_INDEX]:
                loop scale in [0, 1, 2, 3]:
                    loop off in [-257, -1, 0, 256, 32768]:
                        f.code = [Ins(op, dst=6, a=0, b=1, c=i32(size | flags | (scale << 8)), imm=off), Ins(.ret, a=6)]
                        run(f)
    # Direct, indirect, foreign, variadic and guarded calls; debug/fused rows.
    loop op in [Op.call, Op.calli, Op.callc]:
        loop stub in [0..6):
            loop dst in [-1, 6]:
                loop debug in [false, true]:
                    loop mac in [false, true]:
                        f.code = [Ins(op, dst=i32(dst), a=0, b=6, c=i32(stub), imm=4, pos=2), Ins(.ret, a=i32(dst), pos=3)]
                        run(f, debug, mac, debug)
    # All syscall translation policies and error exits; known constants only.
    loop sys in [0, 2, 7, 21, 33, 57, 82, 84, 87, 9999]:
        f.kval[12] = sys
        f.args = [i32(12), i32(0), i32(1), i32(2), i32(3), i32(4)]
        f.code = [Ins(.syscall, dst=6, a=0, b=6), Ins(.ret, a=6)]
        run(f)
        run(f, false, true)
    f.args = [i32(0), i32(1), i32(2), i32(3), i32(4), i32(5)]
    # Constants, FP literal pools, compare fusion, checks and frame reuse.
    loop value in [-9223372036854775807 - 1, -4097, -4096, -1, 0, 4095, 4096, 9223372036854775807]:
        f.code = [Ins(.iconst, dst=7, imm=value), Ins(.fconst, dst=4, imm=value), Ins(.fconst, dst=5, ty=2, imm=value), Ins(.fadd, dst=8, a=4, b=4, ty=1), Ins(.add, dst=6, a=0, b=7), Ins(.eq, dst=9, a=0, b=7), Ins(.if_, a=9), Ins(.checked_add, dst=6, a=6, b=7, imm=4), Ins(.end), Ins(.ret, a=6)]
        run(f, true)
    run(IrFn())
    run(IrFn(nparams=1, vtypes=[i8(0), i8(0)], code=[Ins(.mov, dst=1, a=0), Ins(.ret, a=1)]), true)
    # Independent encoding oracle: VK is an integer operand, never an FP value.
    run(IrFn(nparams=1, vtypes=[i8(0), i8(3)], kval=[0, 0], code=[Ins(.store, a=0, b=1, c=8), Ins(.ret, a=-1)]))
    found = false
    loop p in [2..code.len() / 4):
        if rd32(p * 4) == 0xF900001F: found = true
    assert(found, "canonical zero stores xzr directly through x0")
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_arm64_emitter_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('ir_types', 'ir_operands', 'backend_analysis', 'arm64_allocate', 'arm64_encode', 'arm64_emit')
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
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
