"""Shared backend analysis: frozen reference, every operand shape and reused state."""
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
layouts = ir_operand_layouts()
local_rows: Local[]

render_ir = (ir: IrFn) -> str:
    s = "{ir.nparams} {ir.vtypes} {ir.kval} {ir.args} {ir.dbg_locals}\n"
    loop ins in ir.code: s = s + "{ins.op} {ins.ty} {ins.dst} {ins.a} {ins.b} {ins.c} {ins.imm} {ins.pos}\n"
    s

run = (input: IrFn, debug: bool, wasm: bool, starts: bool, stats: bool = true):
    ir = input
    before = render_ir(input)
    ra_loop_visits = 0
    if debug:
        backend_debug_vregs.clear()
        loop l in ir.dbg_locals:
            if local_rows[l].offset >= 0 or int(local_rows[l].flags) & 12 != 0: continue
            backend_debug_vregs.push(int(local_rows[l].vreg))
    backend_analyze(ir, layouts, debug, wasm, stats, starts)
    assert(render_ir(input) == before and render_ir(ir) == before, "read-only input and snapshot")
    foreign = false
    loop ins in input.code:
        if ins.op == .callc: foreign = true
    assert(x_has_foreign_call == foreign, "foreign calls require an RBP frame; reset for each function")
    print("features {x_has_foreign_call} {x_has_narrow32} {x_has_overflow_pair}; calls {call_pos} {call_w}; loops {loop_s} {loop_e}; visits {ra_loop_visits}")
    loop v in [0..ir.vtypes.len()):
        r = v_live[v]
        print("{v}: {r.first} {r.last} {r.ndef} {r.nuse} {r.weight} {r.next_start} loc {vloc[v]} save {vsave[v]}")
        assert(not vsave[v], "save reset")
        if vloc[v] == LOC_CONST or vloc[v] == LOC_FCONST: print("constant {vcval[v]}")
        if vloc[v] == LOC_SLOT: print("slot {vslot[v]} {vsoff[v]}")
        if vloc[v] == LOC_GLOBAL: print("global {vgkind[v]} {vgoff[v]}")
        if debug: print("keep {dbg_keep[v]}")
    if starts:
        loop pos in [0..ir.code.len() + 1): print("start {pos}: {v_start[pos]}")

main = ():
    local_rows = [Local(offset=-1, vreg=0), Local(offset=-1, vreg=1), Local(offset=0, vreg=2), Local(offset=-1, vreg=3, flags=4), Local(offset=-1, vreg=4, flags=8), Local(offset=-1, vreg=-1), Local(offset=-1, vreg=50), Local(offset=-1, vreg=15)]
    loop debug in [false, true]:
        loop wasm in [false, true]:
            loop starts in [false, true]:
                # Every final opcode, with both conditional indexed-operand forms.
                loop tag in [0..layouts.len()):
                    loop indexed in [false, true]:
                        op = Op(tag)
                        ins = Ins(op, dst=4, a=0, b=2, c=3, imm=257)
                        mode = layouts[tag]
                        if mode & IR_INDEX != 0: ins.c = if indexed: 128 else: 0
                        if op == .zeroslots: ins.b = 3
                        code = [ins]
                        if op == .block or op == .loop or op == .if_: code.push(Ins(.end))
                        if op == .end or op == .else_: code = [Ins(.if_, a=0), ins]
                        if op == .else_: code.push(Ins(.end))
                        if op == .ret and not indexed: code[0].a = -1
                        run(IrFn(nparams=2, vtypes=fill(i8(0), 16), args=[i32(1), i32(3), i32(4)], code=code), debug, wasm, starts)
                # Constants, addresses, canonical constants with holes, repeated
                # definitions, and the slot+constant special case.
                code = [Ins(.iconst, dst=1, imm=2147483647), Ins(.iconst, dst=2, imm=2147483648), Ins(.iconst, dst=3, imm=-2147483648), Ins(.iconst, dst=4, imm=-2147483649), Ins(.fconst, dst=5, imm=-9223372036854775807), Ins(.slot, dst=6, a=7), Ins(.add, dst=7, a=6, b=1), Ins(.gaddr, dst=8, imm=71), Ins(.daddr, dst=9, imm=73), Ins(.mov, dst=9, a=0), Ins(.ret, a=7)]
                types = fill(i8(0), 16)
                types[10] = i8(3)
                run(IrFn(nparams=1, vtypes=types, kval=fill(79, 11), code=code), debug, wasm, starts)
                assert(vloc[1] == LOC_CONST and vloc[2] != LOC_CONST, "signed 32-bit constants")
                assert(vloc[3] == LOC_CONST and vloc[4] != LOC_CONST, "negative constants")
                assert(vloc[7] == LOC_SLOT and vslot[7] == 7 and vsoff[7] == 2147483647, "slot address")
                assert(vloc[9] != LOC_GLOBAL and vloc[10] == LOC_CONST and vcval[10] == 79, "multiple defs and canonical constant")
                # Call policy: nonreturning, cold, register-preserving stubs,
                # intrinsics, inline-copy threshold and terminal failure paths.
                loop c in [0..7):
                    loop size in [0, 1, 2, 256, 257]:
                        code = [Ins(.loop), Ins(.call, dst=4, a=0, b=2, c=i32(c)), Ins(.intr, dst=5, a=0, b=2, imm=size), Ins(.copy, a=0, b=1, imm=size), Ins(.zero, a=0, imm=size), Ins(.end), Ins(.ret, a=4)]
                        run(IrFn(nparams=2, vtypes=fill(i8(0), 16), args=[i32(0), i32(1)], code=code), debug, wasm, starts)
                        assert(call_w.len() == call_pos.len(), "call weights")
                loop op in [Op.call, Op.calli, Op.callc, Op.intr]:
                    loop dst in [-1, 4]:
                        loop other in [0, 4, 10]:
                            code = [Ins(op, dst=i32(dst), a=0, b=1, c=0, imm=2), Ins(.call, dst=-1, a=1, b=1, c=1)]
                            run(IrFn(nparams=1, vtypes=types, kval=fill(79, 11), args=[i32(0), i32(other)], code=code), debug, wasm, starts)
                            terminal = op != .intr and dst >= 0 and (other == dst or other == 10)
                            assert((call_pos.len() == 0) == (terminal and not debug), "terminal failure call")
                # Deep nested and adjacent loops, both cold markers, weighted
                # uses, lifetime extension, debug filtering, stat-off behavior.
                loop depth in [1, 2, 8, 65]:
                    loop cold in [false, true]:
                        code: Ins[]
                        loop i in [0..depth): code.push(Ins(.loop, imm=if cold and i == 1: 1 else: 0))
                        code.push(Ins(.mov, dst=2, a=0))
                        code.push(Ins(.call, dst=1, a=0, b=1, c=2))
                        loop i in [0..depth): code.push(Ins(.end))
                        code.push(Ins(.loop))
                        code.push(Ins(.add, dst=3, a=1, b=2))
                        code.push(Ins(.end))
                        code.push(Ins(.ret, a=3))
                        input = IrFn(nparams=1, vtypes=fill(i8(0), 16), args=[i32(0)], dbg_locals=[0, 1, 2, 3, 4, 5, 6, 7], code=code)
                        run(input, debug, wasm, starts)
                        assert(v_live[0].last >= depth * 2 + 1, "parameter crosses loops")
                        assert(call_w[0] == 1, "explicit cold call")
                        if debug:
                            assert(dbg_keep[0] and dbg_keep[1], "debug locals kept")
                            assert(not dbg_keep[2] and not dbg_keep[3] and not dbg_keep[4] and not dbg_keep[15], "debug exclusions")
                        run(input, debug, wasm, starts, false)
                        assert(ra_loop_visits == 0, "stats disabled")
    # High-water reuse, shrink, and empty input; unused slots must not leak.
    loop count in [512, 4, 0, 300, 1]:
        run(IrFn(vtypes=fill(i8(0), count)), false, false, true)
        loop v in [0..count): assert(vloc[v] == LOC_NONE and v_live[v].last == -1, "reset unused locations")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_backend_analysis_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in ('ir_types', 'ir_operands', 'checker_state', 'backend_analysis'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        imports = ''.join(f"use '{stem}.{extension}'\n" for stem in (
            'ir_types', 'ir_operands', 'checker_state', 'backend_analysis'))
        source.write_text(imports + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith('ok\n')


@pytest.mark.core_quick
def test_backend_analysis_ir_abi():
    """The leaf reads Ins tags/a-b-c through their fixed mixed-language ABI."""
    ir = (ROOT / 'compiler/ir.jo').read_text()
    for name, value in [('VK', 3), ('CALL_IF_SHARED', 3), ('CALL_RC_INC', 4), ('CALL_RC_DEC', 5), ('M_INDEX', 128)]:
        assert re.search(rf'^const {name} = {value}\b', ir, re.M)
    schema = (ROOT / 'compiler/ir_types.dewy').read_text()
    ins = schema.split('Ins:type=[', 1)[1].split(']', 1)[0]
    assert re.findall(r'^\s*(\w+):', ins, re.M)[:6] == ['op', 'ty', 'dst', 'a', 'b', 'c']
