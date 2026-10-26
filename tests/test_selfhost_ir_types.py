"""IR schema ABI and COW snapshots shared by lowering, optimizer and backends."""
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OPCODES = """nop iconst fconst mov add sub mul divs divu rems remu and_ or_ xor shl shrs shru neg not_ eq ne lts les gts ges ltu leu gtu geu fadd fsub fmul fdiv fneg fsqrt fmin fmax ffloor fceil fabs ftrunc feq fne flt fle fgt fge sext8 sext16 sext32 zext8 zext16 zext32 i2f u2f f2i f2f bits2f f2bits load store slot gaddr daddr faddr copy zero memcpy memset zeroslots vop call calli callc syscall intr block loop if_ else_ end br brif ret trap select assume brtable vld vst vbin vsplat vzu mulhs mulhu memeq checked_add checked_sub checked_mul overflow_add overflow_sub overflow_mul rot32 streq findbyte scanbytes findb""".split()
DRIVER = r'''main = ():
    ins = Ins()
    fn = IrFn()
    plan = IrUsePlan()
    print("{size_of(Ins)} {size_of(IrFn)} {size_of(IrUsePlan)}")
    print("{int(&ins.op)-int(&ins)} {int(&ins.ty)-int(&ins)} {int(&ins.dst)-int(&ins)} {int(&ins.a)-int(&ins)} {int(&ins.b)-int(&ins)} {int(&ins.c)-int(&ins)} {int(&ins.imm)-int(&ins)} {int(&ins.pos)-int(&ins)}")
    print("{int(&fn.name)-int(&fn)} {int(&fn.nparams)-int(&fn)} {int(&fn.ret)-int(&fn)} {int(&fn.vtypes)-int(&fn)} {int(&fn.slot_size)-int(&fn)} {int(&fn.slot_align)-int(&fn)} {int(&fn.code)-int(&fn)} {int(&fn.args)-int(&fn)} {int(&fn.cabi)-int(&fn)} {int(&fn.noinline)-int(&fn)} {int(&fn.export_name)-int(&fn)} {int(&fn.fn_index)-int(&fn)} {int(&fn.raw_mem)-int(&fn)} {int(&fn.kval)-int(&fn)} {int(&fn.decl_pos)-int(&fn)} {int(&fn.dbg_locals)-int(&fn)}")
    print("{int(&plan.first)-int(&plan)} {int(&plan.last)-int(&plan)} {int(&plan.ndef)-int(&plan)} {int(&plan.nuse)-int(&plan)} {int(&plan.weight)-int(&plan)} {int(&plan.next_start)-int(&plan)}")
    print("{ins.op} {ins.ty} {ins.dst} {ins.a} {ins.b} {ins.c} {ins.imm} {ins.pos}")
    print("{fn.name}|{fn.nparams} {fn.ret} {fn.vtypes} {fn.slot_size} {fn.slot_align} {fn.code.len()} {fn.args} {fn.cabi} {fn.noinline}|{fn.export_name}|{fn.fn_index} {fn.raw_mem} {fn.kval} {fn.decl_pos} {fn.dbg_locals}")
    print("{plan.first} {plan.last} {plan.ndef} {plan.nuse} {plan.weight} {plan.next_start}")
    loop i in [0..int(Op.findb)+1):
        op = Op(i)
        print("{int(op)} {op}")
    fn = IrFn(name="f", ret=-1, fn_index=9, cabi=true, noinline=true, raw_mem=true, export_name="export", nparams=2, decl_pos=42)
    fn.code.push(Ins(.store, 1, 2, 3, 4, 128, -9223372036854775808, 17))
    fn.args.push(7)
    fn.vtypes.push(3)
    fn.slot_size.push(16)
    fn.slot_align.push(8)
    fn.kval.push(2147483647)
    fn.dbg_locals.push(19)
    saved = fn
    functions = [fn]
    loop i in [0..200): functions.push(IrFn(name="grow", fn_index=i))
    functions[0].code[0].op = .checked_add
    functions[0].code[0].imm = 9223372036854775807
    functions[0].args[0] = -1
    functions[0].vtypes[0] = 5
    functions[0].slot_size[0] = 32
    functions[0].slot_align[0] = 16
    functions[0].kval[0] = -2147483648
    functions[0].dbg_locals[0] = 23
    print("{saved.code[0].op} {saved.code[0].imm} {saved.args} {saved.vtypes} {saved.slot_size} {saved.slot_align} {saved.kval} {saved.dbg_locals}")
    fn = functions[0]
    print("{functions.len()} {fn.code[0].op} {fn.code[0].imm} {fn.args} {fn.vtypes} {fn.slot_size} {fn.slot_align} {fn.kval} {fn.dbg_locals}")
    print("{fn.name} {fn.ret} {fn.fn_index} {fn.cabi} {fn.noinline} {fn.raw_mem} {fn.export_name} {fn.nparams} {fn.decl_pos}")
    plans = [plan]
    plans[0].first = 3
    plans[0].last = 27
    plans[0].ndef = 1
    plans[0].nuse = 4
    plans[0].weight = 8
    plans[0].next_start = 2
    print("{plans[0].first} {plans[0].last} {plans[0].ndef} {plans[0].nuse} {plans[0].weight} {plans[0].next_start} {plan.last}")
'''
EXPECTED = (
    "40 120 48\n"
    "0 4 8 12 16 20 24 32\n"
    "0 8 16 24 32 40 48 56 64 65 72 80 88 96 104 112\n"
    "0 8 16 24 32 40\n"
    "nop 0 0 0 0 0 0 0\n"
    "|0 0 [] [] [] 0 [] false false||0 false [] 0 []\n"
    "1152921504606846976 -1 0 0 0 -1\n"
    + "".join(f"{i} {name}\n" for i, name in enumerate(OPCODES))
    + "store -9223372036854775808 [7] [3] [16] [8] [2147483647] [19]\n"
    "201 checked_add 9223372036854775807 [-1] [5] [32] [16] [-2147483648] [23]\n"
    "f -1 9 true true true export 2 42\n"
    "3 27 1 4 8 2 -1\n"
)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_ir_types_twins(compiler, tmp_path, release):  # noqa: F811
    for extension in ('dewy', 'jo'):
        module = f'ir_types.{extension}'
        (tmp_path / module).write_text((ROOT / 'compiler' / module).read_text())
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(f"use '{module}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == EXPECTED
