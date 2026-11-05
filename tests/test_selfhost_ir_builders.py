"""IR builders, operand views and source-line queries match their frozen twin."""
import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.test_selfhost_ir_types import OPCODES

DRIVER = r'''use 'main.jo'
use 'ir.jo'
use 'ir_types.dewy'
use 'source_types.dewy'
use 'util.jo'
main = ():
    lower_test_cli()
    ir_begin("builders", 7)
    ir_pos = 0; ir_positions = [0]; ir_lines.clear(); ir_cold = false
    assert(ir.name == "builders" and ir.ret == -1 and ir.fn_index == 7)
    a = vreg(VI); b = vreg(VF); c = vreg(VS)
    k = k_vreg(17); assert(k_vreg(17) == k and kv_of(k) == 17)
    assert(is_kv(k) and vtype(k) == VI and not is_kv(a))
    collision = k_vreg(17 xor 65792); assert(kv_of(collision) == (17 xor 65792))
    assert(kv_of(k_vreg(17)) == 17)
    assert(ir_fits32(-2147483648) and ir_fits32(2147483647))
    assert(not ir_fits32(-2147483649) and not ir_fits32(2147483648))
    d = k_vreg_new(21); assert(kv_of(d) == 21)
    assert(new_slot(7, 1) == 0 and new_slot(32, 32) == 1)
    assert(ir.slot_align == [i32(8), i32(32)])
    e_iconst(2147483648); e_iconst(-2147483649)
    e_fconst(-0.0, VF); e_fconst(1.5, VS)
    e_bin(.add, VI, a, k); e_bin(.flt, VF, b, b)
    e_un(.neg, VI, a); e_un(.i2f, VF, a)
    assert(e_mov(a, k) == ir.code.len() - 1); assert(e_addi(a, 0) == a); e_addi(a, 9)
    e_load(VI, a, 8, 8); assert(e_store(a, 16, k, 8) == ir.code.len() - 1)
    e_slot(0); assert(e_copy(a, k, 16) == ir.code.len() - 1); assert(e_vop(a, b, c, 2, 4, VOP_SPLAT_B) == ir.code.len() - 1); assert(e_zero(a, 32) == ir.code.len() - 1)
    e_call0(1, -1); e_call1(2, a, VI); e_call2(3, a, k, VF)
    e_call3(4, a, b, c, VS); e_call4(5, a, b, c, k, -1)
    e_call_span(6, 0, 2, VI); e_call(7, [a, b, c], VI)
    e_calli(a, [b, c], VF, false); e_calli(a, [b], -1, true)
    assert(e_block() == ir.code.len() - 1); assert(e_loop() == ir.code.len() - 1); assert(e_if(a) == ir.code.len() - 1); assert(e_else() == ir.code.len() - 1); assert(e_end() == ir.code.len() - 1)
    assert(e_br(0) == ir.code.len() - 1); assert(e_brif(a, 1) == ir.code.len() - 1); assert(e_brtable(a, [0, 1, 2], 3) == ir.code.len() - 1); assert(e_ret(a) == ir.code.len() - 1); assert(e_trap() == ir.code.len() - 1)
    ir_cold = true; e_call0(8, -1); assert(e_loop() == ir.code.len() - 1)
    n = emit(.call, -1, -1, 0, 0, 1, 9)
    assert(ir.code[n].c == 1 and ir.code[n-2].c == 2 and ir.code[n-1].imm == 1)
    ir_cold = false
    saved = ir
    e_iconst(33); e_call1(9, a, VI)
    assert(saved.code.len() + 1 == ir.code.len() and saved.args.len() + 1 == ir.args.len())
    dump_ir()
    print(ir.vtypes); print(ir.kval); print(ir.args)
    ir.args = [i32(10), i32(11), i32(12), i32(13)]
    loop code in [0..int(Op.findb)+1):
        loop indexed in [0..2):
            ins = Ins(op=Op(code), dst=3, a=0, b=2, c=i32(128*indexed))
            ir.code = [ins]
            d = ir_operands(ins)
            uses: int[]
            loop i in [0..ir_use_count): uses.push(ir_use(i))
            print("{op_name(ins.op)} {indexed} {d} {uses} {ir_has_use(2)} {ir_has_use(99)} {mem_index(ins)} {mem_scale(ins)}")
    ir_operands(Ins(op=.ret, a=-1)); assert(ir_use_count == 0)
    fi = files.len(); files.push(SrcFile(path="/é.dewy", src="a\nb\nc\nd\ne\nf\ng\n"))
    ir_positions = [0]; ir_pos = 0; ir_lines.clear()
    ir_set_pos(0); assert(ir_positions.len() == 1)
    loop off in [0, 2, 12, 4, 6, 8, 10]: ir_set_pos(mkpos(fi, off))
    ir_set_pos(mkpos(fi, 10)); assert(ir_positions.len() == 8)
    assert(ir_line(-1) == 0 and ir_line(99) == 0)
    loop i in [1..8): print(ir_line(i))
    assert(ir_lines == [0, 1, 2, 7, 3, 4, 5, 6])
    ir_begin("next", 8); assert(ir.vtypes.len() == 0 and k_vreg(17) == 0)
    print("ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_ir_builders_twins(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('ir_builders',),
                       jo_doubles=modules_for(source, output, 'ir_builders'))
    assert out.endswith(b'ok\n')
    for opcode in OPCODES:
        assert f'{opcode} 0 '.encode() in out and f'{opcode} 1 '.encode() in out
