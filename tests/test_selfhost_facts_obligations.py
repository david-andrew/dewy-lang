"""Discovery preserves demand order, deferred policy and pending witness snapshots."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAF = ('facts_lifecycle',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'check.jo'
use 'node_store.dewy'
use 'checker_state.dewy'
use 'facts.jo'
use 'directives.jo'
use 'exact.jo'
use 'expr.jo'
use 'nd_contracts.jo'
main = ():
    nodes = fill(Node(), 64)
    exact_marks = fill(u8(0), 64)
    locals = [Local(), Local(flags=i32(LF_ALIAS), alias=2)]
    dir_name_runtime = 1
    dir_name_prototype = 2
    dir_scopes = [DirScope(0, 100, 1, 1)]
    dir_scopes_gen += 1
    nodes[1] = Node(kind=.block, pos=10, list=0, nlist=2)
    nodes[2] = Node(kind=.intrinsic, pos=10, aux=i32(int(IN.static_assert)))
    nodes[3] = Node(kind=.intrinsic, pos=10, aux=i32(int(IN.loan_store)))
    lists = [2, 3]
    fact_panic_collect = true
    fact_panic_pending = []
    fact_has_deferred = false
    if fact_obliged(0) or fact_obliged(-1) or fact_obliged(nodes.len()): exit(11)
    if fact_obliged(1) or not fact_has_deferred or fact_panic_pending != [2, 3]: exit(12)
    saved = fact_panic_pending
    if fact_obliged(2) or saved != [2, 3] or fact_panic_pending != [2, 3, 2]: exit(13)
    fact_panic_pending = []
    fact_has_deferred = false
    dir_scopes[0].value = 0
    dir_scopes_gen += 1
    if not fact_obliged(1) or fact_has_deferred or fact_panic_pending != [2]: exit(14)
    dir_scopes = [DirScope(0, 100, 2, 1)]
    dir_scopes_gen += 1
    fact_panic_pending = []
    if not fact_obliged(1) or fact_panic_pending != [2]: exit(15)
    dir_scopes = [DirScope(0, 100, 1, 1)]
    dir_scopes_gen += 1
    nodes[5] = Node(kind=.exprstmt, pos=10)
    exact_marks[5] = 128
    if not fact_obliged(5): exit(16)
    nodes[6] = Node(kind=.int_lit, pos=10)
    exact_marks[6] = 128
    if fact_obliged(6): exit(17)
    nodes[7] = Node(kind=.ident, pos=10, aux=1, sym=1)
    fact_panic_collect = true
    fact_panic_pending = []
    fact_has_deferred = false
    if fact_obliged(7) or fact_panic_collect or not fact_has_deferred or fact_panic_pending.len() != 0: exit(18)
    nodes[8] = Node(kind=.lambda, pos=10, b=2)
    fact_panic_collect = true
    fact_panic_pending = []
    fact_has_deferred = false
    if fact_obliged(8) or fact_has_deferred or fact_panic_pending != [8]: exit(19)
    nodes[9] = Node(kind=.parallel_region, pos=10, list2=0, nlist2=2)
    fact_panic_collect = true
    fact_panic_pending = []
    fact_has_deferred = false
    if fact_obliged(9) or fact_panic_collect or not fact_has_deferred or fact_panic_pending.len() != 0: exit(20)
    dir_scopes[0].value = 0
    dir_scopes_gen += 1
    if not fact_obliged(9): exit(21)
    dir_scopes[0].value = 1
    dir_scopes_gen += 1
    nodes[13] = Node(kind=.if_, pos=10, a=2, b=3, c=14)
    nodes[14] = Node(kind=.intrinsic, pos=10, aux=i32(int(IN.loan_load)))
    fact_panic_collect = true
    fact_panic_pending = []
    fact_has_deferred = false
    if fact_obliged(13) or not fact_has_deferred or fact_panic_pending != [2, 3, 14]: exit(25)
    dir_forced = true
    fact_panic_pending = []
    fact_has_deferred = false
    if not fact_obliged(13) or fact_has_deferred or fact_panic_pending != [2]: exit(26)
    dir_forced = false
    dir_obligations = true
    fact_panic_pending = []
    if not fact_obliged(13) or fact_has_deferred or fact_panic_pending != [2]: exit(27)
    dir_obligations = false
    loop id in [IN.static_assert, IN.runtime_assert, IN.assert, IN.lend, IN.loan_length, IN.loan_store, IN.loan_address, IN.loan_load, IN.pop, IN.remove, IN.truncate]:
        nodes[12] = Node(kind=.intrinsic, pos=10, aux=i32(int(id)))
        if not fact_obligation_node(12): exit(22)
    nodes[12] = Node(kind=.intrinsic, pos=10, aux=i32(int(IN.len)))
    if fact_obligation_node(12): exit(23)
    nodes[12].aux2 = i32(RANGE_EXHAUSTION)
    if not fact_obligation_node(12): exit(24)
    print("obligation discovery ok")
'''


@pytest.mark.parametrize('release', [False, True])
def test_facts_obligation_discovery_twins(compiler, tmp_path, release):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)


def test_facts_obligation_program_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    globs = ('facts/*.dewy', 'parallel_range_bound/*.dewy', 'saved_operands/*.dewy',
             'effects/*.dewy', 'addr_length/*.dewy', 'witness_bounds/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in globs for p in (ROOT / 'tests/cases').glob(glob)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) > 100
