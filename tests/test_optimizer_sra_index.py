"""Sparse SRA must preserve address ordering, escapes, and workspace isolation."""
from pathlib import Path
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.core_quick
def test_sra_definition_index(compiler, tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'sra-index.jo'
    source.write_text(f"use '{root}/compiler/ir.jo'\nuse '{root}/compiler/opt.jo'\n" + '''
setup = (name: str, nv: int):
    ir_begin(name, 0)
    ir.vtypes = fill(i8(VI), nv)
    ir.slot_size = [i32(16)]
    ir.slot_align = [i32(8)]

# Constant-offset aliases must resolve in definition order, including after
# growing and then shrinking the workspace between functions.
loop nv in [8, 1024, 9]:
    setup("alias", nv)
    ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0),
               Ins(.mov, VI, 1, 0, 0, 0, 0),
               Ins(.iconst, VI, 2, 0, 0, 0, 8),
               Ins(.add, VI, 3, 1, 2, 0, 0),
               Ins(.iconst, VI, 4, 0, 0, 0, 42),
               Ins(.store, VI, 0, 3, 4, 8, 0),
               Ins(.load, VI, 5, 3, 0, 8, 0),
               Ins(.ret, 0, 0, 5, 0, 0, 0)]
    o_sra()
    dump_ir()

# A use preceding the address definition still escapes. Address discovery
# cannot silently turn this into a register-only slot.
setup("forward_escape", 8)
ir.args = [i32(0)]
ir.code = [Ins(.call, VI, -1, 0, 1, 0, 77),
           Ins(.slot, VI, 0, 0, 0, 0, 0),
           Ins(.load, VI, 1, 0, 0, 8, 0),
           Ins(.ret, 0, 0, 1, 0, 0, 0)]
o_sra()
dump_ir()

# A derived address cannot use a constant or base defined later. Its source
# address then escapes through the unrecognized add/move, as in the old walk.
setup("forward_constant", 8)
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0),
           Ins(.add, VI, 2, 0, 1, 0, 0),
           Ins(.iconst, VI, 1, 0, 0, 0, 8),
           Ins(.load, VI, 3, 2, 0, 8, 0),
           Ins(.ret, 0, 0, 3, 0, 0, 0)]
o_sra()
dump_ir()
setup("forward_base", 8)
ir.code = [Ins(.mov, VI, 1, 0, 0, 0, 0),
           Ins(.slot, VI, 0, 0, 0, 0, 0),
           Ins(.load, VI, 2, 1, 0, 8, 0),
           Ins(.ret, 0, 0, 2, 0, 0, 0)]
o_sra()
dump_ir()

# More than one static definition is never an address alias, even if the
# final definition is a move. A cycle must terminate without following it.
setup("redefined", 8)
ir.code = [Ins(.slot, VI, 0, 0, 0, 0, 0),
           Ins(.mov, VI, 1, 0, 0, 0, 0),
           Ins(.mov, VI, 1, 1, 0, 0, 0),
           Ins(.load, VI, 2, 1, 0, 8, 0),
           Ins(.ret, 0, 0, 2, 0, 0, 0)]
o_sra()
dump_ir()

# Iterative address resolution must handle a long chain even when the first
# use appears before the chain's definitions (the slot escapes through it).
setup("long_chain", 4096)
ir.args = [i32(4000)]
ir.code = [Ins(.call, VI, -1, 0, 1, 0, 77), Ins(.slot, VI, 0, 0, 0, 0, 0)]
loop i in [1..4001): ir.code.push(Ins(.mov, VI, i32(i), i32(i - 1), 0, 0, 0))
ir.code.push(Ins(.ret, 0, 0, -1, 0, 0, 0))
o_sra()
print("chain {ir.code.len()} {ir.code[1].op == Op.slot}")
''')
    binary = tmp_path / 'sra-index'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    functions = ran.stdout.split('fn ')[1:]
    assert len(functions) == 7, ran.stdout
    for body in functions[:3]:
        assert 'slot a=' not in body and 'load a=' not in body and 'store a=' not in body, body
    for body in functions[3:]:
        assert 'slot a=' in body and 'load a=' in body, body
    assert 'chain 4003 true' in ran.stdout, ran.stdout[-1000:]


def test_optimizer_input_operand_contract(compiler, tmp_path):
    """Fused metadata must agree with the IR's operand ABI for every opcode."""
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'operand-contract.jo'
    source.write_text(f"use '{root}/compiler/ir.jo'\nuse '{root}/compiler/opt.jo'\n" + '''
loop k in [0..int(Op.findb) + 1):
    op = Op(k)
    if op == .block or op == .loop or op == .if_ or op == .else_ or op == .end: continue
    loop indexed in [0, M_INDEX]:
        ir_begin("operands", 0)
        ir.nparams = 16
        ir.vtypes = fill(i8(VI), 16)
        ir.args = [i32(0), i32(5), i32(6), i32(0), i32(0)]
        mode = if op == .load or op == .store: 8 | indexed else: 3
        ins = Ins(op, VI, 4, 1, 2, i32(mode), 0)
        expected = fill(false, 16)
        ir_operands(ins)
        loop u in [0..ir_use_count): expected[ir_use(u)] = true
        ir.code = [ins, Ins(.ret, 0, 0, 0, 0, 0, 0)]
        optimize()
        loop v in [0..16):
            first = if expected[v]: 0 else if v == 0: 1 else: 2147483647
            last = if v == 0: 1 else if expected[v]: 0 else: -1
            if int(o_regs[v].first) != first or int(o_lastuse[v]) != last:
                print("mismatch {k} {indexed} {v}: {o_regs[v].first}/{o_lastuse[v]} != {first}/{last}")
print("operands ok")
''')
    binary = tmp_path / 'operand-contract'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'operands ok\n', ran.stdout
