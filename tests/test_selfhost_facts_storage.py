"""fact_storage_loop/scan/target preserve ordered inventories and nested snapshots."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAF = ('facts_index_proofs',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'expr.jo'
use 'types.jo'
use 'type_ops.dewy'
use 'facts.jo'
use 'facts_index_proofs.dewy'
use 'lower.jo'
use 'lower_analysis.dewy'
reset_storage = ():
    fp_bases = []; fp_kill = []; fp_escape = []; fp_written = []
    fp_calls = false; fp_lambda = false
main = ():
    init_types()
    nodes = fill(Node(), 160)
    locals = fill(Local(), 8)
    lpath_ids.clear(); lpath_parents = [0]
    a = mk_array(T_INT)
    aa = mk_array(a)
    locals[1] = Local(owner=1, flags=i32(LF_DECL), type=i32(aa))
    locals[2] = Local(owner=1, flags=i32(LF_DECL), type=i32(a))
    nodes[1] = Node(kind=.ident, aux=i32(int(SK.local)), sym=1, type=i32(aa))
    nodes[2] = Node(kind=.ident, aux=i32(int(SK.local)), sym=2, type=i32(a))
    nodes[3] = Node(kind=.int_lit, type=i32(T_INT), ival=1)
    nodes[4] = Node(kind=.index, a=1, b=3, type=i32(a))
    nodes[5] = Node(kind=.assign, a=4, b=3)
    nodes[6] = Node(kind=.index, a=2, b=3, aux=1, type=i32(a))
    nodes[7] = Node(kind=.intrinsic, aux=i32(int(IN.len)), type=i32(T_INT))
    set_list(7, [1])
    nodes[8] = Node(kind=.intrinsic, aux=i32(int(IN.resize)))
    set_list(8, [2, 3])
    nodes[9] = Node(kind=.addr, a=1)
    nodes[10] = Node(kind=.lambda, b=9)
    nodes[12] = Node(kind=.block)
    set_list(12, [4, 5, 6, 8])
    nodes[13] = Node(kind=.block)
    set_list(13, [14, 14])
    nodes[14] = Node(kind=.while_, a=7, b=12)
    nodes[15] = Node(kind=.for_, a=2, b=13, flags=i32(NF_MUT))
    k1:int = int(lpath_key(1)); k2:int = int(lpath_key(2))
    fp_bases = [91]; fp_kill = [92]; fp_escape = [93]; fp_written = [94]
    fp_calls = true; fp_lambda = true
    outer = fact_storage_loop(15)
    if fp_bases != [91] or fp_kill != [92] or fp_escape != [93] or fp_written != [94] or not fp_calls or not fp_lambda: exit(11)
    if outer.bases != [1, 1, 2, 1, 1, 2] or outer.kill != [k2, k2] or outer.escape != [k2, k2] or outer.written != [k1, k1] or outer.calls or outer.opaque: exit(12)
    if not fact_storage_cache.has(14) or not fact_storage_cache.has(15): exit(13)
    reset_storage()
    fact_storage_scan(15, 0)
    if fp_bases != outer.bases or fp_kill != [k2, k2, k2] or fp_escape != [k2, k2, k2] or fp_written != outer.written: exit(14)
    # Cached nested records and retained callers survive scratch mutation.
    prior = fact_storage_cache
    saved = fp_bases
    fact_storage_scan(4, 0)
    if saved != outer.bases or fp_bases.len() != saved.len() + 1: exit(15)
    nodes[14].b = 9
    hit = fact_storage_loop(14)
    if hit.bases != [1, 1, 2] or hit.calls: exit(16)
    fact_storage_cache.clear()
    fresh = fact_storage_loop(14)
    if fresh.bases.len() != 0 or fresh.kill != [k1] or not fresh.calls: exit(17)
    if not prior.has(15) or (prior.get(14) ?? FactStorage()).bases != [1, 1, 2]: exit(18)
    loop i in [32..112):
        nodes[i] = Node(kind=.while_, b=4)
        grown = fact_storage_loop(i)
        if grown.bases != [1] or grown.calls or grown.opaque: exit(19)
    if outer.bases != [1, 1, 2, 1, 1, 2] or prior.len() != 2: exit(20)
    # Nested element targets and a field projection recurse to the same root.
    nodes[16] = Node(kind=.index, a=4, b=3, type=i32(T_INT))
    nodes[17] = Node(kind=.field, a=16, aux=-3, type=i32(T_INT))
    reset_storage()
    fact_storage_target(17)
    fact_storage_target(2)
    if fp_written != [k1] or fp_bases != [1] or fp_kill != [k2]: exit(21)
    # An element alias kills its source array, including through a target field.
    nodes[18] = Node(kind=.for_, a=1)
    locals[3] = Local(owner=1, flags=i32(LF_ELEMALIAS), alias=18, type=i32(T_INT))
    nodes[19] = Node(kind=.ident, aux=i32(int(SK.local)), sym=3, type=i32(T_INT))
    nodes[20] = Node(kind=.field, a=19, aux=-3, type=i32(T_INT))
    reset_storage()
    fact_storage_scan(19, 0)
    fact_storage_target(20)
    if fp_kill != [k1, k1] or fp_bases.len() != 0: exit(22)
    # Mutating intrinsics kill paths; measurements do not copy or kill them.
    loop id in [IN.push, IN.pop, IN.insert, IN.remove, IN.clear, IN.reserve, IN.resize, IN.truncate, IN.extend]:
        nodes[21] = Node(kind=.intrinsic, aux=i32(int(id)))
        set_list(21, [2, 3])
        reset_storage()
        fact_storage_scan(21, 0)
        if fp_kill != [k2] or fp_escape.len() != 0 or fp_lambda: exit(23)
    loop id in [IN.len, IN.arrcap]:
        nodes[21].aux = i32(int(id))
        reset_storage()
        fact_storage_scan(21, 0)
        if fp_kill.len() != 0 or fp_escape.len() != 0 or fp_lambda: exit(24)
    # Opaque operations stop at the boundary; lambdas never walk their bodies.
    loop id in [IN.arrdata, IN.syscall]:
        nodes[21].aux = i32(int(id))
        reset_storage()
        fact_storage_scan(21, 0)
        if not fp_lambda or fp_kill.len() != 0: exit(25)
    reset_storage()
    fact_storage_scan(10, 0)
    if not fp_lambda or not fp_calls or fp_kill.len() != 0: exit(26)
    nodes[22] = Node(kind=.fn_, b=9)
    reset_storage()
    fact_storage_scan(22, 0)
    if not fp_lambda or fp_kill.len() != 0: exit(27)
    # A mutable call actual that is an element follows the target path.
    ft = types.len()
    types.push(TypeInfo(kind=.fn_, mutmask=1))
    nodes[23] = Node(kind=.ident, aux=i32(int(SK.local)), sym=4, type=i32(ft))
    nodes[24] = Node(kind=.call, aux=1, a=23, type=i32(T_INT))
    set_list(24, [4])
    reset_storage()
    fact_storage_scan(24, 0)
    if fp_written != [k1] or fp_bases != [1, 1] or not fp_calls or fp_lambda: exit(28)
    set_list(24, [1])
    reset_storage()
    fact_storage_scan(24, 0)
    if fp_kill != [k1] or fp_escape != [int(lpath_key(23)), k1]: exit(29)
    print("storage summaries ok")
'''


@pytest.mark.parametrize('release', [False, True])
def test_facts_storage_twins(compiler, tmp_path, release):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)


def test_facts_storage_program_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    globs = ('loop_copy/*.dewy', 'loop_bounds/*.dewy', 'slice/*.dewy', 'fixed/*.dewy', 'loop/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in globs for p in (ROOT / 'tests/cases').glob(glob)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) > 60
