"""Borrowed optimizer views preserve snapshots and follow register growth."""
import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_opt_cleanup import function
from tests.test_selfhost_opt_rewrite import build_run


DRIVER = r'''
ir: IrFn
checked_flags = true
const VI = 0
const M_INDEX = 128
cache_values = fill(0, 256)
cache_regs = fill(0, 256)
cache_epochs = fill(0, 256)

main = ():
    opt_decode = o_decode
    opt_operands = data(ir_operand_layout)
    opt_kc_val = data(cache_values)
    opt_kc_reg = data(cache_regs)
    opt_kc_epoch = data(cache_epochs)
    opt_use_values = &opt_use_tuple as *int
    opt_working = &opt_working_storage as *Ins
    opt_ir = &ir
    # Rebind after both growing and shrinking the current function. A call
    # must rewrite its argument span without changing an earlier IR snapshot.
    loop count in [4, 256, 4]:
        ir = IrFn(nparams=1, vtypes=fill(i8(0), count), args=[i32(1)], code=[Ins(.mov, dst=1, a=0), Ins(.call, dst=2, a=0, b=1), Ins(.ret, a=2)])
        saved = ir
        o_resize(count)
        opt_kc_fn += 1
        opt_rewrite()
        assert(ir.args[0] == 0 and saved.args[0] == 1, "argument snapshot")
        assert(saved.code[0].op == .mov and saved.vtypes.len() == count, "IR snapshot")
        assert(opt_args == data(ir.args), "argument view")
        # Ordinary, canonical-constant and cleanup-temporary allocation all
        # grow vtypes; retained snapshots force detachment as well as growth.
        saved = ir
        loop i in [0..1024):
            v = ow_vreg(i % 3)
            assert(ow_vtype(v) == i % 3 and opt_vtypes == data(ir.vtypes), "ordinary growth")
            k = ow_k_vreg(100000 + i)
            assert(ow_is_kv(k) and ow_vtype(k) == 0 and opt_vtypes == data(ir.vtypes), "constant growth")
        t = oc_tmp()
        assert(oc_vtype(t) == 0 and opt_vtypes == data(ir.vtypes), "cleanup growth")
        assert(saved.vtypes.len() == count, "type snapshot")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_opt_borrowed_views(compiler, tmp_path, release):  # noqa: F811
    original = (ROOT / 'compiler/opt.jo').read_text()
    decode = original[original.index('o_rewrite_mask ='):original.index('const MIN_INT')]
    decode += '\n'.join(function(original, name) for name in (
        'o_pure_classify', 'cse_arity_classify', 'o_defines_classify',
        'kills_memory_classify', 'o_retargetable_classify', 'o_resize'))
    driver = '\nir_operand_layout = ir_operand_layouts()\n' + decode + DRIVER
    outputs = [build_run(compiler, tmp_path, ext, driver, release) for ext in ('dewy', 'jo')]
    assert outputs == ['ok\n', 'ok\n']
