"""Record-stride loop queries match frozen Jo over small instruction runs."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

JO = {
    'ir.jo': "const VF = 1\nconst M_INDEX = 4\nuse_of: int[][]\n",
    'loops.jo': '''use 'ir_types.dewy'
struct CLoop:
    pl: int
    pe: int
    ctr: int
    endv: int
    inc: int
    signed: bool
lx_within = (code: Ins[], v: int, L: CLoop) -> bool: v != 99
lx_def_at = (code: Ins[], v: int, s: int, e: int) -> int:
    at = -1
    loop p in [s..e):
        if int(code[p].dst) == v:
            if at >= 0: return -1
            at = p
    at
''',
    'ir_builders.dewy': '''$runtime_checks

from p"ir_types.dewy" import (Ins)
from p"ir.jo" import (M_INDEX use_of)
let current:int64=0
is_kv=(v:int64):>bool=>{v >=? 1000}
kv_of=(v:int64):>int64=>{v - 1000}
mem_index=(ins:Ins):>int64=>{
    if int64(ins.c) & M_INDEX =? 0 {return -1}
    int64(ins.b)
}
mem_scale=(ins:Ins):>int64=>{(int64(ins.c) >> 8) & 3}
ir_operands=(ins:Ins):>int64=>{
    current=int64(ins.imm)
    0
}
ir_has_use=(v:int64):>bool=>{use_of[current].contains(v)}
''',
    'ir_builders.jo': '''use 'ir_types.jo'
use 'ir.jo'
current = 0
is_kv = (v: int) -> bool: v >= 1000
kv_of = (v: int) -> int: v - 1000
mem_index = (ins: Ins) -> int:
    if int(ins.c) & M_INDEX == 0: return -1
    int(ins.b)
mem_scale = (ins: Ins) -> int: (int(ins.c) >> 8) & 3
ir_operands = (ins: Ins) -> int:
    current = int(ins.imm)
    0
ir_has_use = (v: int) -> bool: use_of[current].contains(v)
''',
}

DRIVER = r'''
use 'ir.jo'
use 'loops.jo'
use 'ir_types.dewy'
use 'ir_builders.dewy'
ins = (op: Op, ty: int = 0, dst: int = 0, a: int = 0, b: int = 0, c: int = 0, uses: int[] = []) -> Ins:
    use_of.push(uses)
    Ins(op=op, ty=i32(ty), dst=i32(dst), a=i32(a), b=i32(b), c=i32(c), imm=use_of.len() - 1)
row = (code: Ins[], L: CLoop, shl_at: int, load_at: int):
    print("{lx_record_index(code, L, shl_at)} {lx_record_stride(code, L, code[load_at])}")
main = ():
    use_of.push([])
    L = CLoop(pl=0, pe=6, ctr=5, inc=5)
    shl = (shift: int) -> Ins: ins(.shl, 0, 20, 5, 1000 + shift)
    load = (dst: int) -> Ins: ins(.load, 1, dst, 7, 20, 4, [20])
    pad = () -> Ins: ins(.nop)
    loop shift in [3, 4, 5, 6, 7]:
        row([pad(), shl(shift), load(30), pad(), pad(), pad(), pad()], L, 1, 2)
    # Each way the index stops being memory-only, or the access stops being record-like.
    row([pad(), ins(.add, 0, 20, 5, 1004), load(30), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), ins(.shl, 0, 20, 6, 1004), load(30), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), ins(.shl, 0, 20, 5, 4), load(30), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), ins(.shl, 0, 99, 5, 1004), load(30), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), shl(4), shl(4), load(30), pad(), pad(), pad()], L, 1, 3)
    row([pad(), load(30), shl(4), pad(), pad(), pad(), pad()], L, 2, 1)
    row([pad(), shl(4), ins(.add, 0, 31, 20, 1, 0, [20]), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), shl(4), ins(.load, 0, 30, 7, 20, 4, [20]), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), shl(4), ins(.load, 1, 30, 7, 20, 4 | 256, [20]), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), shl(4), ins(.load, 1, 30, 7, 21, 4, [20]), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), shl(4), ins(.load, 1, 30, 7, 20, 0, [20]), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), shl(4), ins(.load, 1, 30, 20, 20, 4, [20]), pad(), pad(), pad(), pad()], L, 1, 2)
    row([pad(), shl(4), pad(), pad(), pad(), pad(), pad()], L, 1, 2)
    # (the stride searches only before the increment)
    row([pad(), pad(), pad(), pad(), pad(), pad(), shl(4), load(30)], CLoop(pl=0, pe=8, ctr=5, inc=5), 6, 7)
    # (its own use in the checked run is skipped; a use in another position counts)
    row([pad(), ins(.shl, 0, 20, 5, 1006, 0, [20]), load(30), load(31), pad(), pad(), pad()], L, 1, 3)
    print("ordered ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_loop_ordered_twins(compiler, tmp_path, release):
    output = compare_narrow(compiler, tmp_path, release, ('ir_types', 'loop_ordered'), DRIVER, doubles=JO)
    assert output.endswith(b'ordered ok\n')
    lines = output.split(b'\n')
    assert lines[0] == b'false 0' and lines[1] == b'true 16' and lines[3] == b'true 64' and lines[4] == b'false 0'
