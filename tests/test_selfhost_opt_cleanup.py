"""The final cleanup unit: frozen twin, independent operands and flow producer."""
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
ir: IrFn

run = (code: Ins[], nv: int, native: bool = true) -> Ins[]:
    ir = IrFn(code=code, vtypes=fill(i8(VI), nv), args=[i32(2), i32(3), i32(4)])
    o_reg_storage.clear()
    o_reg_storage.resize(nv)
    loop v in [0..nv):
        o_reg_storage[v].repl = i32(v)
        o_reg_storage[v].dop = -1
    loop ins in code:
        d = ir_operands(ins)
        if d >= 0:
            o_reg_storage[d].ndef += 1
            if ins.op == .iconst:
                o_reg_storage[d].constant = true
                o_reg_storage[d].cval = ins.imm
        loop k in [0..ir_use_count): o_reg_storage[ir_use(k)].nuse += 1
    # Parameters may have no instruction definition; each is still stable.
    loop v in [0..nv):
        if o_reg_storage[v].ndef == 0: o_reg_storage[v].ndef = 1
        o_reg_storage[v].stable = o_reg_storage[v].ndef == 1
    o_fact_scope.resize(nv * 2)
    o_fact_nbr.resize(nv * 2)
    opt_ir = &ir
    opt_args = data(ir.args)
    opt_vtypes = data(ir.vtypes)
    opt_input_count = ir.code.len()
    o_count = 0
    o_capacity = max(1, code.len())
    o_out_storage.resize(o_capacity)
    o_out = data(o_out_storage)
    ow_flow_begin()
    loop ins in code: ow_append(ins)
    if o_flow_dead: ow_flow_end_dead()
    o_regs = data(o_reg_storage)
    o_reg_count = nv
    opt_decode = o_decode
    opt_operands = data(ir_operand_layout)
    opt_checked_flags = native
    saved = ir
    result = opt_cleanup(o_out, o_count)
    assert(saved.vtypes.len() == nv and saved.code.len() == code.len(), "IR snapshot")
    assert(o_reg_count == o_reg_storage.len(), "published register count")
    assert(o_regs == data(o_reg_storage), "refreshed register view")
    assert(o_fact_scope.len() == o_reg_storage.len() * 2 and o_fact_nbr.len() == o_reg_storage.len() * 2, "fact workspace growth")
    loop v in [nv..ir.vtypes.len()):
        assert(o_reg_storage[v].ndef == 1 and o_reg_storage[v].stable and o_reg_storage[v].repl == i32(v), "new register identity")
        assert(o_reg_storage[v].defpos == -1 and o_reg_storage[v].first == 2147483647 and o_reg_storage[v].dop == -1, "new register defaults")
    print("case {nv} {native}: {result.len()} {ir.vtypes.len()} {o_reg_count}")
    loop ins in result: print("{ins.op} {ins.ty} {ins.dst} {ins.a} {ins.b} {ins.c} {ins.imm} {ins.pos}")
    result

main = ():
    opt_ir = &ir
    opt_args = data(ir.args)
    opt_vtypes = data(ir.vtypes)
    opt_input_count = ir.code.len()
    # The leaf's raw tag and descriptor reads must agree with the independent
    # optimizer walker, for every opcode and exceptional operand form.
    ir.args = [i32(2), i32(3), i32(4)]
    opt_args = data(ir.args)
    opt_decode = o_decode
    opt_operands = data(ir_operand_layout)
    loop tag in [0..int(Op.findb) + 1):
        loop mode in [0..2):
            loop count in [0..3):
                ins = Ins(Op(tag), 0, 5, 0, i32(count), i32(2 | (mode * M_INDEX)), 0)
                if ins.op == .ret and mode == 0: ins.a = -1
                assert(oc_tag(&ins) == tag, "raw opcode ABI")
                ir_operands(ins)
                loop v in [-1..8): assert(oc_has_use(&ins, v) == ir_has_use(v), "independent operand view")
    # Empty and nop-only input; dead nested control, calls and loop exits.
    assert(run([], 0).len() == 0, "empty")
    assert(run([Ins(.nop)], 1).len() == 0, "nop")
    run([Ins(.block), Ins(.ret, a=-1, pos=11), Ins(.loop), Ins(.trap), Ins(.end), Ins(.end)], 1)
    run([Ins(.block), Ins(.brif, a=0), Ins(.trap), Ins(.end), Ins(.ret, a=-1)], 1)
    run([Ins(.loop), Ins(.br), Ins(.end), Ins(.ret, a=-1)], 1)
    run([Ins(.block), Ins(.call, dst=-1, c=1), Ins(.iconst, dst=0, imm=9), Ins(.end)], 1)
    # Remove redundant wrappers and branches; preserve source positions.
    r = run([Ins(.block), Ins(.iconst, dst=0, imm=42, pos=17), Ins(.br), Ins(.end), Ins(.ret, a=0)], 1)
    assert(r.len() == 2 and r[0].op == .iconst and r[0].pos == 17, "pure wrapper")
    r = run([Ins(.if_, a=0), Ins(.br, imm=2), Ins(.end)], 1)
    assert(r.len() == 1 and r[0].op == .brif and r[0].imm == 1, "conditional exit")
    run([Ins(.block), Ins(.lts, dst=2, a=0, b=1), Ins(.brif, a=2), Ins(.br, imm=1), Ins(.end)], 3)
    # Retarget only single-use equal-width results, and honor native flag rules.
    loop native in [false, true]:
        r = run([Ins(.checked_add, dst=2, a=0, b=1), Ins(.mov, dst=3, a=2), Ins(.ret, a=3)], 4, native)
        assert(r.len() == (if native: 2 else: 3), "checked retarget policy")
    run([Ins(.add, dst=2, a=0, b=1), Ins(.store, a=3, b=0), Ins(.mov, dst=3, a=2), Ins(.ret, a=3)], 4)
    run([Ins(.add, dst=2, a=0, b=1), Ins(.mov, ty=1, dst=3, a=2), Ins(.ret, a=3)], 4)
    # Two value arms allocate fresh registers. Repeating the call exercises
    # reuse after the small workspace grows, including both failure-guard arms.
    loop guard in [0..3):
        code = [Ins(.block), Ins(.block), Ins(.brif, a=0, pos=71)]
        if guard == 1: code.push(Ins(.if_, a=1)); code.push(Ins(.call, dst=-1, c=1)); code.push(Ins(.end))
        code.push(Ins(.add, dst=4, a=1, b=2))
        code.push(Ins(.br, imm=1))
        code.push(Ins(.end))
        if guard == 2: code.push(Ins(.if_, a=1)); code.push(Ins(.call, dst=-1, c=1)); code.push(Ins(.end))
        code.push(Ins(.sub, dst=4, a=2, b=3))
        code.push(Ins(.end))
        code.push(Ins(.ret, a=4))
        r = run(code, 5)
        found = false
        loop ins in r:
            if ins.op == .select:
                assert(ins.pos == 71, "select source position")
                found = true
        assert(found and ir.vtypes.len() >= 7, "diamond selects and grows")
    # Unsafe speculation and result/input interference reject the diamond.
    loop op in [Op.load, Op.divs, Op.call, Op.add]:
        run([Ins(.block), Ins(.block), Ins(.brif, a=0), Ins(op, dst=3, a=1, b=2), Ins(.br, imm=1), Ins(.end), Ins(.sub, dst=3, a=3, b=1), Ins(.end), Ins(.ret, a=3)], 5)
    # A unique vector temporary can be retargeted; an aliased slot cannot.
    loop aliases in [0..2):
        code = [Ins(.slot, dst=0, a=0), Ins(.slot, dst=1, a=1)]
        if aliases > 0: code.push(Ins(.slot, dst=2, a=0))
        code.push(Ins(.vop, a=0, b=3, c=4, imm=32))
        code.push(Ins(.copy, a=1, b=0, imm=8))
        run(code, 5)
    print("ok")
'''


def function(text, name):
    return re.search(rf'^{name} =.*?(?=^\w|\Z)', text, re.M | re.S)[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_opt_cleanup_twins(compiler, tmp_path, release):  # noqa: F811
    original = (ROOT / 'compiler/opt.jo').read_text()
    decode = original[original.index('o_rewrite_mask ='):original.index('const MIN_INT')]
    decode += '\n'.join(function(original, name) for name in (
        'o_pure_classify', 'cse_arity_classify', 'o_defines_classify',
        'kills_memory_classify', 'o_retargetable_classify'))
    rewrite = (ROOT / 'compiler/opt_rewrite.jo').read_text()
    flow = '\n'.join(function(rewrite, name) for name in (
        'ow_flow_begin', 'ow_flow_exit', 'ow_flow_end_dead', 'ow_flow_emit',
        'ow_flow_pop', 'ow_grow_output', 'ow_append_plain', 'ow_append'))
    ir = (ROOT / 'compiler/ir.jo').read_text()
    walker = ir[ir.index('ir_use_count = 0'):ir.index('ir_operand_layout: int[]')]
    outputs = []
    for extension in ('dewy', 'jo'):
        for stem in ('ir_types', 'ir_operands', 'opt_workspace', 'opt_cleanup'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{stem}.{extension}').write_text(text)
        imports = ''.join(f"use '{stem}.{extension}'\n" for stem in (
            'ir_types', 'ir_operands', 'opt_workspace', 'opt_cleanup'))
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(imports + '\nconst VI = 0\nconst M_INDEX = 128\n'
                          'checked_flags = true\nir_operand_layout = ir_operand_layouts()\n'
                          + decode + flow + walker + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=15)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith('ok\n')
