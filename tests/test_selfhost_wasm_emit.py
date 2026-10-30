"""Whole-function wasm encoder: frozen bytes, allocation, signatures and reuse."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
render = (f: IrFn) -> str:
    s = "{f.vtypes}:{f.args}:{f.kval}:{f.slot_size}:{f.slot_align}\n"
    loop i in f.code: s += "{i.op} {i.ty} {i.dst} {i.a} {i.b} {i.c} {i.imm} {i.pos}\n"
    s

run = (input: IrFn):
    before = render(input)
    first, last = wasm_live(input)
    body = wasm_body(input)
    assert(render(input) == before, "input and shared snapshot preserved")
    print("live {first}:{last}")
    print("body {body}; error {wasm_error}; sites {w_sites}; locals {loc_of}; slots {slot_offs}; frame {cur_frame}; maximum {max_frame}")
    print("signatures {type_sigs}; table {table_funcs}")

main = ():
    wfn_index = [0, 7, 13, 17, 21, 27, 31, 37]
    wasm_import_results = [-2, WT_I32, WT_I64, WT_F32, WT_F64, -1, WT_I32, -2]
    wasm_import_params = [[], [WT_I32, WT_I64, WT_I32], [WT_I64, WT_I64, WT_I64], [WT_F32, WT_I64, WT_I32], [WT_F64, WT_I64, WT_I32], [WT_I32, WT_I32, WT_I32], [WT_I32], []]
    wasm_grow = [false, false, false, false, false, false, true, false]
    wasm_user_pos = [false, true, false, true]
    wasm_mt_active_off = 33
    wasm_data_size = 57
    data_base = 4096
    types = fill(i8(0), 16)
    types[4] = i8(1)
    types[5] = i8(2)
    types[12] = i8(3)
    f = IrFn(nparams=2, ret=-1, vtypes=types, args=[i32(0), i32(1), i32(2), i32(3), i32(4), i32(5)], kval=fill(9223372036854775807, 13), slot_size=[i32(1), i32(9), i32(17), i32(32)], slot_align=[i32(1), i32(8), i32(16), i32(32)])
    # Every IR opcode and every scalar type; unsupported native operations must
    # return the same status rather than silently producing an instruction.
    loop tag in [0..107):
        loop ty in [-1, 0, 1, 2]:
            ins = Ins(Op(tag), ty=i32(ty), dst=6, a=0, b=2, c=1, imm=1, pos=1)
            if ins.op == .vop: ins.imm = 32 | VOP_SPLAT_B | VOP_SPLAT_C
            if ins.op == .load or ins.op == .store: ins.c = 8
            f.code = [ins]
            if ins.op == .loop or ins.op == .block or ins.op == .if_: f.code.push(Ins(.end))
            if ins.op == .end: f.code = [Ins(.block), ins]
            if ins.op == .else_: f.code = [Ins(.if_, a=0), ins, Ins(.end)]
            run(f)
    # Full memory addressing matrix, including negative offsets, index scales,
    # signed loads, all widths and typed stores.
    loop op in [Op.load, Op.store]:
        loop size in [1, 2, 4, 8]:
            loop flags in [0, M_SIGNED, M_FLOAT, M_INDEX, M_SIGNED | M_INDEX, M_FLOAT | M_INDEX]:
                loop scale in [0, 1, 2, 3]:
                    loop off in [-129, 0, 127, 16384]:
                        loop value in [0, 4, 5]:
                            f.code = [Ins(op, dst=6, a=0, b=i32(value), c=i32(size | flags | (scale << 8)), imm=off)]
                            run(f)
    # Calls: internal, every import ABI, grow special case, guarded RC stubs,
    # nonreturning calls, source filtering, discarded and retained results.
    loop lf in [0..8):
        loop stub in [0..6):
            loop dst in [-1, 6]:
                loop pos in [0..4):
                    f.code = [Ins(.call, dst=i32(dst), a=0, b=1, c=i32(stub), imm=lf, pos=i32(pos))]
                    run(f)
    loop op in [Op.calli, Op.callc]:
        loop ty in [-1, 0, 1, 2]:
            f.code = [Ins(op, ty=i32(ty), dst=-1, a=0, b=3, c=0, pos=3), Ins(op, ty=i32(ty), dst=6, a=0, b=3, c=1, pos=2)]
            run(f)
    # Overflow encodings, signed and unsigned; IEEE bits and LEB boundaries.
    loop op in [Op.checked_add, Op.checked_sub, Op.checked_mul]:
        loop unsigned in [0, 1]:
            f.code = [Ins(op, dst=6, a=0, b=1, c=i32(unsigned), imm=7, pos=1)]
            run(f)
    loop value in [-9223372036854775807 - 1, -16385, -129, -65, -64, -1, 0, 63, 64, 127, 128, 16384, 9223372036854775807]:
        f.code = [Ins(.iconst, dst=6, imm=value), Ins(.mov, dst=7, a=6), Ins(.add, dst=8, a=7, b=12), Ins(.fconst, ty=1, dst=4, imm=value), Ins(.fconst, ty=2, dst=5, imm=value), Ins(.ret, a=8)]
        run(f)
    # Local reuse and stable tied starts, loop extension, shadow-stack frame
    # restoration, all zero-slot forms and empty/smaller functions after growth.
    loop depth in [1, 2, 32]:
        f.code = []
        loop k in [0..depth): f.code.push(Ins(.loop))
        f.code.push(Ins(.zeroslots, a=0, b=6))
        f.code.push(Ins(.add, dst=6, a=0, b=1))
        f.code.push(Ins(.add, dst=7, a=6, b=0))
        f.code.push(Ins(.faddr, dst=8, imm=7))
        f.code.push(Ins(.call, dst=9, a=0, b=1, imm=0))
        loop k in [0..depth): f.code.push(Ins(.end))
        f.code.push(Ins(.ret, a=7))
        run(f)
    run(IrFn())
    run(IrFn(nparams=1, vtypes=[i8(0), i8(0)], code=[Ins(.mov, dst=1, a=0), Ins(.ret, a=1)]))
    assert(cur_frame == 0 and loc_of == [0, 1], "fresh frame and locals after reused workspace")
    before_table = table_funcs
    run(IrFn(vtypes=[i8(0)], code=[Ins(.mulhs), Ins(.faddr, imm=2)]))
    assert(wasm_error == 1 and table_funcs == before_table, "stop at unsupported native instruction")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_wasm_emitter_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in ('ir_types', 'ir_operands', 'leb128', 'wasm_emit'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use 'ir_types.{extension}'\nuse 'wasm_emit.{extension}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith('ok\n')


def test_wasm_emitter_ir_constants():
    """The closed encoder's small numeric ABI follows the shared IR schema."""
    import re

    ir = (ROOT / 'compiler/ir.jo').read_text()
    emitter = (ROOT / 'compiler/wasm_emit.dewy').read_text()
    names = ('VI', 'VF', 'VS', 'VK', 'M_SIGNED', 'M_FLOAT', 'M_INDEX',
             'VOP_SPLAT_B', 'VOP_SPLAT_C', 'CALL_IF_SHARED', 'CALL_RC_INC', 'CALL_RC_DEC')
    for name in names:
        old = re.search(rf'^const {name} = (\w+)', ir, re.M)
        new = re.search(rf'^const {name} = (\w+)', emitter, re.M)
        assert old and new and int(old[1], 0) == int(new[1], 0), name
