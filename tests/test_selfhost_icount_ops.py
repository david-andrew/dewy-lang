"""`--time`'s buckets, sides and reports match frozen Jo; a failing counter reads as no work."""
import re

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

STATE = re.sub(r"(?m)^(use '[^']*'|#.*)\n", '', (ROOT / 'compiler/icount.jo').read_text())
SERVICES = r'''use 'source_types.dewy'
use 'node_store.dewy'
use 'checker_state.dewy'
const NF_LAZY = 4
const DC_LAZY_SPAN = -315
const LK_INST = 0
struct ModuleD:
    is_prelude: bool
    file: i32
struct LFuncD:
    kind: int
    inst: int
struct ReaderD:
    dc_lazy_span_end: {int: int}
struct ParserD:
    reader: ReaderD
nodes: Node[] = [Node()]
lists: i32[]
fns: FnInst[] = [FnInst()]
modules: ModuleD[]
lfuncs: LFuncD[]
files: SrcFile[]
lib_root = ""
pl_on = false
pl_files: int[]
pl_units: int[]
pl_reached: int[]
pl_inst_decls: int[]
dc_parser: ParserD
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
kids2 = (n: int) -> int[]: node_kids2(nodes, lists, n)
kid_c = (n: int) -> int: int(nodes[n].c)
kid_d = (n: int) -> int: int(nodes[n].d)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
pos_file = (p: int) -> int: p >> 20
pos_off = (p: int) -> int: p & 0xFFFFF
code_lines = (src: str, a: int, b: int) -> int:
    n = 0
    loop i in [a..b):
        if src[i] == '\n': n += 1
    n
'''

DRIVER = r'''
use 'icount.jo'
at = (f: int, off: int) -> int: (f << 20) | off
n_ = (k: NK, pos: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> int:
    nodes.push(Node(kind=k, pos=pos, a=i32(a), b=i32(b), c=i32(c), d=i32(d)))
    nodes.len() - 1
state = (): print("{ic_on} {ic_bucket} {ic_last} {ic_counts}")
main = ():
    # Off: nothing is charged.
    print(ic_switch(IC_LOAD, IC_ROOT)); ic_restore(3); print(ic_fn(1, 1)); print(ic_lf(1, 1)); print(ic_mod(1, 1)); print(ic_phase(1))
    ic_report(); ic_lines_report()
    state()
    # Sides.
    files = [SrcFile(path="/lib/a.jo", src="one\ntwo\nthree\n"), SrcFile(path="/home/b.jo", src="four\nfive\n\nsix"), SrcFile(path="/lib/c.jo", src="")]
    modules = [ModuleD(true, 0), ModuleD(false, 1), ModuleD(false, 0), ModuleD(false, 9), ModuleD(false, -1)]
    loop m in [-1, 0, 1, 2, 3, 4, 5]: print(ic_side_mod(m))
    lib_root = "/lib"
    loop m in [-1, 0, 1, 2, 3, 4, 5]: print(ic_side_mod(m))
    fns.push(FnInst(mod=1)); fns.push(FnInst(mod=0))
    loop f in [-1, 0, 1, 2, 3]: print(ic_side_fn(f))
    lfuncs = [LFuncD(LK_INST, 1), LFuncD(LK_INST, 2), LFuncD(1, 1)]
    loop lf in [-1, 0, 1, 2, 3]: print(ic_side_lf(lf))
    # On, with no counter: every read gives the last value back.
    ic_on = true; ic_fd = -1; ic_counts = fill(0, IC_PHASES * 3); ic_last = 100
    print(ic_read())
    print(ic_switch(IC_CHECK, IC_ROOT)); state()
    print(ic_fn(IC_FACTS, 1)); state()
    print(ic_fn(IC_EFFECTS, 2)); state()
    print(ic_lf(IC_LOWER, 0)); state()
    print(ic_lf(IC_OPT, 2)); state()
    print(ic_mod(IC_EMIT, 1)); state()
    print(ic_phase(IC_OTHER)); state()
    ic_restore(5); state()
    # The report: rows with counts only, totals by side, nodes by whose source they come from.
    ic_counts[IC_LOAD * 3 + IC_ROOT] = 11
    ic_counts[IC_CHECK * 3 + IC_ROOT] = 22
    ic_counts[IC_LOWER * 3 + IC_LIB] = 33
    ic_counts[IC_OTHER * 3 + IC_SHARED] = 44
    n_(.int_lit, at(0, 1)); n_(.int_lit, at(1, 1)); n_(.int_lit, at(1, 2)); n_(.int_lit, 0); n_(.int_lit, at(9, 1))
    ic_report()
    state()
    # Declaration lines over every child slot; only its own file's positions count.
    leaf = n_(.int_lit, at(1, 6))
    far = n_(.int_lit, at(1, 12))
    other_file = n_(.int_lit, at(0, 13))
    nowhere = n_(.int_lit, 0)
    list_kid = n_(.int_lit, at(1, 10))
    second_kid = n_(.int_lit, at(1, 11))
    d = n_(.fn_, at(1, 8), leaf, far, other_file, nowhere)
    node_set_list(mut nodes, mut lists, d, [list_kid])
    node_set_list2(mut nodes, mut lists, d, [second_kid])
    print(ic_decl_lines(d))
    print(ic_decl_lines(n_(.int_lit, at(9, 1))))
    print(ic_decl_lines(n_(.int_lit, 0)))
    print(ic_decl_lines(n_(.int_lit, at(2, 0))))
    # Lines processed.
    ic_lines_report()
    pl_on = true
    ic_lines_report()
    pl_files = [0, 1]
    pl_units = [0, 0, 8]
    pl_reached = [0, 0, 4]
    lazy = n_(.block, at(0, 1)); nodes[lazy].flags = i32(NF_LAZY); nodes[lazy].ival = 0; nodes[lazy].aux = 8
    plain = n_(.block, at(0, 1))
    outside = n_(.block, at(9, 1)); nodes[outside].flags = i32(NF_LAZY)
    waiting = n_(.block, at(0, 1)); nodes[waiting].ival = 0; nodes[waiting].aux2 = DC_LAZY_SPAN
    dc_parser.reader.dc_lazy_span_end[waiting] = 4
    away = n_(.block, at(9, 1)); nodes[away].aux2 = DC_LAZY_SPAN
    dc_parser.reader.dc_lazy_span_end[away] = 4
    # (a body read already: its block holds the body, and its span from the file's start is not waiting)
    read = n_(.block, at(0, 1)); nodes[read].ival = 0
    dc_parser.reader.dc_lazy_span_end[read] = 8
    # (the same span twice, as a copied declaration leaves it: counted once)
    twin = n_(.block, at(0, 1)); nodes[twin].flags = i32(NF_LAZY); nodes[twin].ival = 0; nodes[twin].aux = 8
    pl_reached = [0, 0, 4, 0, 0, 4]
    pl_inst_decls = [d, d, leaf]
    ic_lines_report()
    print("counts ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_icount_ops_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare_narrow(compiler, tmp_path, release, ('source_types', 'node_store', 'checker_types', 'checker_state', 'icount_ops'), DRIVER,
                            doubles={'services.jo': SERVICES, 'icount.jo': STATE}, services=('check', 'lower', 'util', 'ast', 'dewy_context', 'lazy_bodies'))
    assert output.endswith(b'counts ok\n')
