"""Closed optimizer rewrite unit: scalar oracle and complete frozen-twin IR."""
import random
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_opt_cleanup import function


MODULES = ('ir_types', 'ir_operands', 'opt_workspace', 'opt_cleanup', 'opt_rewrite')


def build_run(compiler, directory, extension, driver, release):
    for stem in MODULES:
        text = (ROOT / f'compiler/{stem}.{extension}').read_text()
        if extension == 'jo':
            text = text.replace(".dewy'", ".jo'")
        (directory / f'{stem}.{extension}').write_text(text)
    imports = ''.join(f"use '{stem}.{extension}'\n" for stem in MODULES)
    source, binary = directory / 'driver.jo', directory / 'driver'
    source.write_text(imports + driver)
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=90)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
    return ran.stdout


DRIVER = r'''
ir: IrFn
checked_flags = true
const VI = 0
const M_INDEX = 128
cache_values = fill(0, 256)
cache_regs = fill(0, 256)
cache_epochs = fill(0, 256)

run = (code: Ins[], nv: int, policy: int = 0, raw: bool = false):
    ir = IrFn(code=code, vtypes=fill(i8(0), nv), nparams=min(nv, 4), args=[i32(0), i32(1), i32(2), i32(0), i32(1)], raw_mem=raw)
    o_resize(nv)
    opt_decode = o_decode
    opt_operands = data(ir_operand_layout)
    opt_checked_flags = policy != 1
    opt_rotate32_ok = policy != 1
    opt_mulh_ok = policy != 2
    opt_kc_val = data(cache_values)
    opt_kc_reg = data(cache_regs)
    opt_kc_epoch = data(cache_epochs)
    opt_kc_fn += 1
    opt_use_values = &opt_use_tuple as *int
    before = ir
    opt_ir = &ir
    opt_working = &opt_working_storage as *Ins
    opt_rewrite()
    assert(before.code.len() == code.len() and before.vtypes.len() == nv, "borrowed input snapshot")
    assert(o_regs == data(o_reg_storage), "fresh register view")
    assert(o_out == data(o_out_storage), "fresh output view")
    print("{ir.code.len()} {ir.vtypes.len()} {o_reg_count}")
    loop ins in ir.code: print("{ins.op} {ins.ty} {ins.dst} {ins.a} {ins.b} {ins.c} {ins.imm} {ins.pos}")
    loop ty in ir.vtypes: print("t {ty}")
    loop k in ir.kval: print("k {k}")
    loop a in ir.args: print("a {a}")

main = ():
    opt_ir = &ir
    ir.args = [i32(2), i32(3), i32(4)]
    opt_decode = o_decode
    opt_operands = data(ir_operand_layout)
    opt_use_values = &opt_use_tuple as *int
    # Every descriptor and exceptional operand form, independently decoded.
    loop tag in [0..int(Op.findb) + 1):
        assert(ow_boolean_tag(tag) == o_boolean_op(Op(tag)), "boolean tag ABI")
        loop mode in [0..2):
            assert(ow_arity(tag, mode * M_INDEX) == cse_arity(Op(tag), mode * M_INDEX), "arity tag ABI")
            loop count in [0..3):
                ins = Ins(Op(tag), 0, 5, 0, i32(count), i32(2 | (mode * M_INDEX)), 0)
                if ins.op == .ret and mode == 0: ins.a = -1
                assert(ow_operands(&ins) == ir_operands(ins), "definition descriptor")
                assert(opt_use_count == ir_use_count, "operand count")
                loop k in [0..ir_use_count): assert(ow_use(k) == ir_use(k), "operand identity")
    run([], 0)
    # Full workspace reset/reuse, CSE, replacement and register growth.
    loop size in [1, 128, 7, 512, 1]:
        code: Ins[]
        loop i in [0..size):
            code.push(Ins(.add, dst=i32(i + 4), a=0, b=1, pos=i32(i + 10)))
        code.push(Ins(.ret, a=i32(size + 3)))
        run(code, size + 4)
    loop policy in [0..3):
        # Native and wasm strength reduction, magic division, signed powers,
        # unsigned high-bit divisors, checked arithmetic and rotate recognition.
        loop op in [Op.mul, Op.divs, Op.divu, Op.rems, Op.remu, Op.add, Op.checked_add, Op.checked_sub, Op.checked_mul]:
            loop divisor in [-9223372036854775807 - 1, -17, -8, -1, 0, 1, 2, 3, 7, 8, 13, 65537, 9223372036854775807]:
                loop flags in [0, 1, 32, 33]:
                    run([Ins(.iconst, dst=4, imm=divisor), Ins(op, dst=5, a=0, b=4, c=i32(flags), pos=47), Ins(.ret, a=5)], 6, policy)
        run([Ins(.iconst, dst=4, imm=13), Ins(.iconst, dst=5, imm=19), Ins(.shl, dst=6, a=0, b=4), Ins(.shru, dst=7, a=0, b=5), Ins(.or_, dst=8, a=6, b=7), Ins(.zext32, dst=9, a=8), Ins(.ret, a=9)], 10, policy)
    # Structured scopes, facts, conditional and unconditional exits, branch
    # tables, unreachable code and mutable loop definitions/memory generations.
    run([Ins(.block), Ins(.if_, a=0), Ins(.add, dst=4, a=1, b=2), Ins(.else_), Ins(.add, dst=4, a=1, b=3), Ins(.end), Ins(.brif, a=0), Ins(.trap), Ins(.end), Ins(.ret, a=4)], 5)
    run([Ins(.block), Ins(.loop), Ins(.load, dst=4, a=0), Ins(.add, dst=1, a=1, b=2), Ins(.store, a=0, b=1), Ins(.brif, a=1), Ins(.end), Ins(.ret, a=4), Ins(.end)], 5)
    run([Ins(.block), Ins(.block), Ins(.brtable, a=0, b=2, c=3, imm=1), Ins(.trap), Ins(.end), Ins(.ret, a=1), Ins(.end)], 4)
    run([Ins(.block), Ins(.iconst, dst=4, imm=0), Ins(.if_, a=4), Ins(.loop), Ins(.add, dst=1, a=1, b=2), Ins(.br), Ins(.end), Ins(.else_), Ins(.sub, dst=1, a=1, b=2), Ins(.end), Ins(.end), Ins(.ret, a=1)], 5)
    loop raw in [false, true]:
        loop mode in [0, 32, 64, 128, 160, 192]:
            run([Ins(.load, dst=4, a=0, b=1, c=i32(mode)), Ins(.store, dst=2, a=0, b=3, c=i32(mode)), Ins(.load, dst=5, a=0, b=1, c=i32(mode)), Ins(.add, dst=6, a=4, b=5), Ins(.ret, a=6)], 7, raw=raw)
    # Frozen call-argument spans and the indirect function operand.
    loop op in [Op.call, Op.calli, Op.callc, Op.intr, Op.syscall]:
        run([Ins(.mov, dst=4, a=0), Ins(op, dst=5, a=0, b=3, c=4), Ins(.ret, a=5)], 6)
    run([Ins(.faddr, dst=4, imm=123), Ins(.calli, dst=5, a=0, b=3, c=4), Ins(.ret, a=5)], 6)
    # Mutable copies must survive their source's later overwrite.
    run([Ins(.mov, dst=4, a=0), Ins(.add, dst=0, a=1, b=2), Ins(.add, dst=5, a=0, b=4), Ins(.ret, a=5)], 6)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_opt_rewrite_twins(compiler, tmp_path, release):  # noqa: F811
    original = (ROOT / 'compiler/opt.jo').read_text()
    decode = original[original.index('o_rewrite_mask ='):original.index('const MIN_INT')]
    decode += '\n'.join(function(original, name) for name in (
        'o_pure_classify', 'cse_arity_classify', 'o_defines_classify',
        'kills_memory_classify', 'o_retargetable_classify', 'o_resize'))
    ir = (ROOT / 'compiler/ir.jo').read_text()
    walker = ir[ir.index('ir_use_count = 0'):ir.index('ir_operand_layout: int[]')]
    driver = '\nir_operand_layout = ir_operand_layouts()\n' + decode + walker + DRIVER
    outputs = [build_run(compiler, tmp_path, ext, driver, release) for ext in ('dewy', 'jo')]
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith('ok\n')


MASK = (1 << 64) - 1


def wrap(x):
    return (x + (1 << 63)) % (1 << 64) - (1 << 63)


def ref(op, x, y):
    if op.startswith('overflow_'):
        z = {'overflow_add': x + y, 'overflow_sub': x - y, 'overflow_mul': x * y}[op]
        return 1, int(z != wrap(z))
    if op in ('divs', 'rems'):
        if y == 0 or (x == -(1 << 63) and y == -1):
            return 0, 0
        q = (abs(x) // abs(y)) * (-1 if (x < 0) != (y < 0) else 1)
        return 1, q if op == 'divs' else x - q * y
    value = {
        'add': x + y, 'sub': x - y, 'mul': x * y,
        'and_': x & y, 'or_': x | y, 'xor': x ^ y,
        'shl': x << (y & 63), 'shrs': x >> (y & 63), 'shru': (x & MASK) >> (y & 63),
        'eq': x == y, 'ne': x != y,
        'lts': x < y, 'les': x <= y, 'gts': x > y, 'ges': x >= y,
        'ltu': (x & MASK) < (y & MASK), 'leu': (x & MASK) <= (y & MASK),
        'gtu': (x & MASK) > (y & MASK), 'geu': (x & MASK) >= (y & MASK),
    }[op]
    return 1, wrap(value)


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_opt_word_oracle(compiler, tmp_path, release):  # noqa: F811
    values = [-(1 << 63), -(1 << 63) + 1, -(1 << 32), -65537, -129,
              -65, -64, -63, -8, -7, -3, -2, -1, 0, 1, 2, 3, 7, 8,
              31, 32, 63, 64, 65, 127, 255, 65536, (1 << 31) - 1,
              1 << 31, (1 << 32) - 1, 1 << 32, (1 << 63) - 1]
    rng = random.Random(51)
    values += [rng.randrange(-(1 << 63), 1 << 63) for _ in range(8)]
    binary_ops = ('overflow_add overflow_sub overflow_mul add sub mul divs rems '
                  'and_ or_ xor shl shrs shru eq ne lts les gts ges ltu leu gtu geu').split()
    unary_ops = 'neg not_ sext8 sext16 sext32 zext8 zext16 zext32'.split()
    driver = '\nmain = ():\n    xs: int[] = [' + ', '.join(map(str, values)) + ']\n'
    driver += ('    loop op in [' + ', '.join('Op.' + op for op in binary_ops) + ']:\n'
               '        loop x in xs:\n            loop y in xs:\n'
               '                ok, value = ow_fold(op, x, y)\n'
               '                print("{int(ok)} {value}")\n')
    driver += ('    loop op in [' + ', '.join('Op.' + op for op in unary_ops) + ']:\n'
               '        loop x in xs:\n            ok, value = ow_fold_un(op, x)\n'
               '            print("{int(ok)} {value}")\n')
    expected = []
    for op in binary_ops:
        for x in values:
            for y in values:
                expected.append(ref(op, x, y))
    for op in unary_ops:
        for x in values:
            if op == 'neg':
                value = -x
            elif op == 'not_':
                value = ~x
            else:
                bits = int(op[4:])
                value = x & ((1 << bits) - 1)
                if op.startswith('sext') and value & (1 << (bits - 1)):
                    value -= 1 << bits
            expected.append((1, wrap(value)))
    for extension in ('dewy', 'jo'):
        output = build_run(compiler, tmp_path, extension, driver, release)
        actual = [tuple(map(int, row.split())) for row in output.splitlines()]
        assert actual == expected
