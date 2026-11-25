"""Positive bounds preserve overflow guards, cache epochs and write summaries."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAF = ('facts_index_proofs',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'check.jo'
use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_tokens.dewy'
use 'refinement_types.dewy'
use 'facts.jo'
use 'expr.jo'
use 'types.jo'
use 'type_ops.dewy'
use 'exact.jo'
use 'lower.jo'
use 'math_lower.jo'
use 'directives.jo'
main = ():
    init_types()
    nodes = fill(Node(), 128)
    exact_marks = fill(u8(0), 200)
    locals = fill(Local(), 8)
    fns = [FnInst(), FnInst()]
    cur_fn = 1
    locals[1] = Local(owner=1, flags=i32(LF_DECL), type=i32(T_INT))
    locals[2] = Local(owner=1, flags=i32(LF_DECL), type=i32(T_MATH_INT))
    locals[3] = Local(owner=2, flags=i32(LF_DECL), type=i32(T_INT))
    nodes[1] = Node(kind=.int_lit, type=i32(T_INT), ival=5)
    nodes[2] = Node(kind=.int_lit, type=i32(T_INT), ival=0)
    nodes[3] = Node(kind=.int_lit, type=i32(T_INT), ival=-1)
    nodes[4] = Node(kind=.int_lit, type=i32(T_INT), ival=9223372036854775807)
    nodes[5] = Node(kind=.int_lit, type=i32(T_INT), ival=1)
    nodes[6] = Node(kind=.int_lit, type=i32(T_INT), ival=2)
    nodes[7] = Node(kind=.int_lit, type=i32(T_U8))
    nodes[8] = Node(kind=.int_lit, type=i32(T_I32), ival=5)
    nodes[9] = Node(kind=.int_lit, type=i32(T_INT), ival=5, flags=i32(NF_U64))
    if positive_bound(0, false) != -1 or positive_bound(3, false) != -1: exit(11)
    if positive_bound(7, false) != 255 or positive_bound(8, false) != -1 or positive_bound(9, false) != -1: exit(12)
    nodes[10] = Node(kind=.binary, type=i32(T_INT), op=i32(int(Tok.plus)), a=1, b=6)
    nodes[11] = Node(kind=.binary, type=i32(T_INT), op=i32(int(Tok.plus)), a=4, b=5)
    nodes[12] = Node(kind=.binary, type=i32(T_INT), op=i32(int(Tok.star)), a=4, b=6)
    nodes[13] = Node(kind=.binary, type=i32(T_INT), op=i32(int(Tok.star)), a=4, b=2)
    nodes[14] = Node(kind=.binary, type=i32(T_INT), op=i32(int(Tok.amp)), a=3, b=1)
    nodes[15] = Node(kind=.binary, type=i32(T_INT), op=i32(int(Tok.percent)), a=3, b=6, aux2=-1)
    if positive_bound(10, false) != 7 or positive_bound(11, false) != -1 or positive_bound(12, false) != -1: exit(13)
    if positive_bound(13, false) != 0 or positive_bound(14, false) != 5 or positive_bound(15, false) != 1: exit(14)
    nodes[16] = Node(kind=.conv, type=i32(T_U8), aux=i32(int(CV.int_)), a=4)
    if positive_bound(16, false) != 255: exit(15)
    exact_marks[16] = 1
    if positive_bound(16, false) != 9223372036854775807: exit(16)
    nodes[17] = Node(kind=.conv, type=i32(T_INT), aux=i32(int(CV.fixed_store)), a=1)
    if positive_bound(17, false) != 5: exit(17)
    positive_cache = []; positive_stamp = []; positive_epoch = 1
    if positive_bound(1, true) != 5 or positive_cache.len() != nodes.len(): exit(18)
    saved_cache = positive_cache
    saved_stamp = positive_stamp
    nodes[1].ival = 6
    if positive_bound(1, true) != 5 or positive_bound(1, false) != 6: exit(19)
    positive_epoch += 1
    if positive_bound(1, true) != 6 or saved_cache[1] != 5 or saved_stamp[1] != 1: exit(20)
    nodes.resize(200)
    nodes[199] = Node(kind=.int_lit, type=i32(T_INT), ival=13)
    if positive_bound(199, true) != 13 or positive_cache.len() != 200 or saved_cache.len() != 128: exit(21)
    positive_bounds = {}
    positive_local_write(1, 5)
    saved_bounds = positive_bounds
    positive_local_write(1, 2)
    positive_local_write(1, 8)
    if (positive_bounds.get(1) ?? -1) != 8 or (saved_bounds.get(1) ?? -1) != 5: exit(22)
    positive_local_write(1, -1)
    positive_local_write(1, 10)
    positive_local_write(3, 10)
    if (positive_bounds.get(1) ?? 0) != -1 or positive_bounds.has(3): exit(23)
    locals[2].flags = i32(LF_DECL | LF_PARAM)
    positive_local_write(2, 4)
    if positive_bounds.has(2): exit(24)
    locals[2].flags = i32(LF_DECL)
    nodes[20] = Node(kind=.ident, type=i32(T_INT), aux=i32(int(SK.local)), sym=1)
    nodes[21] = Node(kind=.ident, type=i32(T_MATH_INT), aux=i32(int(SK.local)), sym=2)
    positive_bounds[1] = 8
    positive_bounds_fn = cur_fn
    nonneg_locals = [1, 1]; nonneg_limits = [7, 11]
    if positive_bound_value(20, true) != 7 or positive_bound_value(20, false) != -1: exit(25)
    math_word_limits[1] = 9
    if positive_bound_value(20, true) != 9: exit(26)
    math_word_limits.clear(); nonneg_locals = []; nonneg_limits = []
    if positive_bound_value(20, true) != 8: exit(27)
    lists = [20, 21]
    nodes[22] = Node(kind=.tuple, list=0, nlist=2)
    positive_target_write(22, 4)
    if (positive_bounds.get(1) ?? 0) != -1 or (positive_bounds.get(2) ?? 0) != -1: exit(28)
    positive_bounds.clear()
    nodes[23] = Node(kind=.vardecl, sym=1, b=6)
    positive_write(23)
    if (positive_bounds.get(1) ?? -1) != 2: exit(29)
    nodes[24] = Node(kind=.assign, a=20, b=1, op=i32(int(Tok.assign)))
    positive_write(24)
    if (positive_bounds.get(1) ?? -1) != 6: exit(30)
    nodes[24].op = i32(int(Tok.pluseq))
    positive_write(24)
    if (positive_bounds.get(1) ?? 0) != -1: exit(31)
    positive_bounds_fn = -1
    math_writes_ready = false
    fns[1].writes_ready = true
    fns[1].write_sites = [23]
    prior = positive_bounds
    if positive_bound_value(20, true) != 2 or positive_bounds_fn != 1 or positive_collecting_writes: exit(32)
    if (prior.get(1) ?? 0) != -1: exit(33)
    fns[1].kind = FK_LAMBDA
    fns[1].params = [1]
    locals[1].flags = 0
    fact_parallel_bounds[1] = FactBound(0, 12)
    if positive_bound_value(20, false) != 12: exit(34)
    locals[1].flags = i32(LF_ASSIGNED)
    if positive_bound_value(20, false) != -1: exit(35)
    nodes[30] = Node(kind=.ident, type=i32(mk_array(T_INT)))
    lists = [30]
    nodes[31] = Node(kind=.intrinsic, type=i32(T_INT), aux=i32(int(IN.len)), list=0, nlist=1, pos=10)
    if positive_bound_value(31, false) != (1 << 56) / 8: exit(36)
    dir_name_assumed_bounds = 77
    dir_scopes = [DirScope(0, 100, 77, 1)]
    dir_scopes_gen += 1
    if positive_bound_value(31, false) != -1: exit(37)
    dir_scopes = []; dir_scopes_gen += 1
    dir_assumed_bounds_any = true
    positive_collecting_writes = true
    if positive_bound_value(31, false) != -1: exit(38)
    positive_collecting_writes = false
    if positive_bound_value(31, false) < 0: exit(39)
    print("positive bounds ok")
'''


@pytest.mark.parametrize('release', [False, True])
def test_facts_positive_bounds_twins(compiler, tmp_path, release):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)


def test_facts_positive_program_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    globs = ('notraps17_word/*.dewy', 'exact_int/*.dewy', 'math_int_join/*.dewy',
             'parallel_range_bound/*.dewy', 'loop_bounds/*.dewy', 'loop_copy/*.dewy',
             'bigint/*.dewy', 'product_bounds/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in globs for p in (ROOT / 'tests/cases').glob(glob)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) > 30
