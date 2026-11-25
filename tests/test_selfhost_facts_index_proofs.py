"""Range/index proofs retain snapshots, ordering, caps and mutation boundaries."""
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
use 'facts.jo'
use 'expr.jo'
use 'types.jo'
use 'type_ops.dewy'
use 'lower.jo'
main = ():
    init_types()
    nodes = fill(Node(), 96)
    locals = fill(Local(), 8)
    cur_fn = 1
    locals[1] = Local(owner=1, type=i32(mk_array(T_INT)))
    locals[2] = Local(owner=1, type=i32(T_INT))
    locals[3] = Local(owner=1, type=i32(T_INT))
    nodes[1] = Node(kind=.int_lit, type=i32(T_INT), ival=0)
    nodes[2] = Node(kind=.int_lit, type=i32(T_INT), ival=4)
    nodes[3] = Node(kind=.int_lit, type=i32(T_INT), ival=-1)
    nodes[4] = Node(kind=.conv, type=i32(T_MATH_INT), aux=i32(int(CV.int_)), a=2)
    nodes[5] = Node(kind=.conv, type=i32(T_INT), aux=i32(int(CV.int_)), a=4)
    if word_integer_value(5) != 2 or not is_nonneg(5) or is_nonneg(3): exit(11)
    nodes[6] = Node(kind=.binary, type=i32(T_INT), op=i32(int(Tok.plus)), a=2, b=2)
    if is_nonneg(6): exit(12)
    if not stable_loop_index(2) or stable_loop_index(-1): exit(13)
    locals[2].flags = i32(LF_ASSIGNED)
    if stable_loop_index(2): exit(14)
    locals[2].flags = 0
    nodes[7] = Node(kind=.ident, type=locals[1].type, aux=i32(int(SK.local)), sym=1)
    lists = [7]
    nodes[8] = Node(kind=.intrinsic, type=i32(T_INT), aux=i32(int(IN.len)), list=0, nlist=1)
    if fixed_array_len(8) != 1 or not fixed_array_local(1): exit(15)
    locals[1].flags = i32(LF_RESIZED)
    if fixed_array_len(8) != -1 or fixed_array_local(1): exit(16)
    locals[1].flags = 0
    nodes[9] = Node(kind=.ident, type=i32(T_INT), aux=i32(int(SK.local)), sym=2)
    nodes[10] = nodes[9]
    if not same_value(9, 10) or same_value(0, 0) or not same_value(5, 5): exit(17)
    locals[2].flags = i32(LF_ASSIGNED)
    if same_value(9, 10): exit(18)
    locals[2].flags = 0
    nonneg_locals = [2]
    if not is_nonneg(9): exit(19)
    nodes[11] = Node(kind=.range, a=1, b=8)
    if not nonnegative_range(11) or range_bounds_arrays(11) != [1]: exit(20)
    nodes[11].flags = i32(NF_INCLUSIVE)
    if range_bounds_arrays(11).len() != 0: exit(21)
    nodes[11].flags = i32(NF_STEP)
    nodes[11].c = 1
    if nonnegative_range(11): exit(22)
    nodes[11].c = 2
    if not nonnegative_range(11): exit(23)
    nodes[12] = Node(kind=.ident, type=i32(T_INT), aux=i32(int(SK.local)), sym=3)
    len_of_local[3] = 1
    nodes[11].flags = 0
    nodes[11].b = 12
    if range_bounds_arrays(11) != [1]: exit(24)
    array_len_expr[1] = 12
    if range_bounds_arrays(11) != [1, 1]: exit(25)
    safe_index = [(1, 2, false)]
    if index_safety(7, 9) != 1: exit(26)
    safe_index = [(1, 2, true)]
    if index_safety(7, 9) != 2 or index_safety(7, 12) != 0: exit(27)
    nodes[13] = Node(kind=.index, a=7, b=9)
    nodes[14] = Node(kind=.index, a=7, b=12)
    seen = fill(false, nodes.len())
    saved = seen
    if other_index_of(13, 1, [2], seen) or not seen[13] or saved[13]: exit(28)
    if not other_index_of(14, 1, [2], seen): exit(29)
    if other_index_of(14, 1, [2], seen) or other_index_of(96, 1, [], seen): exit(30)
    nodes[15] = Node(kind=.return_)
    lists.push(15)
    nodes[16] = Node(kind=.block, list=1, nlist=1)
    nodes[17] = Node(kind=.binary, type=i32(T_BOOL), op=i32(int(Tok.lt)), a=8, b=2)
    nodes[18] = Node(kind=.if_, a=17, b=16)
    lower_length_guards = []
    lower_length_guard(18)
    if lower_length_guards != [(1, 4)]: exit(31)
    guards = lower_length_guards
    loop _ in [0..20): lower_length_guard(18)
    if lower_length_guards.len() != 16 or guards != [(1, 4)]: exit(32)
    positive_epoch += 1
    if index_safety(7, 1) != 1 or index_safety(7, 2) != 0: exit(33)
    fns = [FnInst(), FnInst(no_indexes=true)]
    len_of_local.clear()
    array_len_expr.clear()
    nodes[11].b = 8
    nodes[19] = Node(kind=.for_, a=11, b=13, sym=2)
    safe_index = []
    nonneg_locals = []
    nonneg_limits = []
    positive_epoch = 9223372036854775807
    outer = range_facts_begin(19, 2)
    if outer != (0, 1, true) or safe_index != [(1, 2, false)] or nonneg_locals != [2]: exit(34)
    if positive_epoch != -9223372036854775807 - 1: exit(35)
    saved_indices = safe_index
    saved_nonneg = nonneg_locals
    saved_limits = nonneg_limits
    inner = range_facts_begin(19, 2)
    if inner != outer or safe_index.len() != 2 or nonneg_locals != [2, 2]: exit(36)
    if saved_indices != [(1, 2, false)] or saved_nonneg != [2] or saved_limits.len() != 1: exit(37)
    range_facts_end(inner)
    if safe_index != saved_indices or nonneg_locals != saved_nonneg or nonneg_limits != saved_limits: exit(38)
    range_facts_end(outer)
    if safe_index.len() != 0 or nonneg_locals.len() != 0 or nonneg_limits.len() != 0: exit(39)
    if positive_epoch != -9223372036854775807 + 2: exit(40)
    print("index proofs ok")
'''


@pytest.mark.parametrize('release', [False, True])
def test_facts_index_proofs_twins(compiler, tmp_path, release):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)


def test_facts_index_proofs_program_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    globs = ('bounds/*.dewy', 'facts/*.dewy', 'index_scope/*.dewy',
             'notraps17_word/*.dewy', 'addr_length/*.dewy', 'loops/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in globs for p in (ROOT / 'tests/cases').glob(glob)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) > 100
