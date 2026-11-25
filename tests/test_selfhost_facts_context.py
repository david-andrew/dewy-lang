"""Broadcast construction and demand/context queries preserve the frozen Jo contract."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly

LEAVES = ('facts_values', 'facts_lifecycle')
CONTEXT = '''use 'main.jo'
use 'facts.jo'
use 'facts_lifecycle.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'util.jo'
use 'source_types.dewy'
use 'exact.jo'
use 'directives.jo'
main = ():
    files = [SrcFile(path="/lib/prelude.jo", is_dewy=false), SrcFile(path="/app/main.dewy", is_dewy=true), SrcFile(path="/lib/math.dewy", is_dewy=true)]
    modules = [Module(file=0), Module(file=1), Module(file=2), Module(file=-1), Module(file=3)]
    fns = [FnInst(mod=0, body=1)]
    nodes = fill(Node(), 8)
    nodes[1] = Node(pos=0)
    lib_root = "/lib/"
    # The module, including file zero, wins over a conflicting body position.
    if not fn_in_lib(0) or fn_dewy(0): exit(10)
    nodes[1].pos = mkpos(1, 12)
    if not fn_in_lib(0) or fn_dewy(0): exit(11)
    fns[0].mod = 1
    nodes[1].pos = mkpos(2, 12)
    if fn_in_lib(0) or not fn_dewy(0): exit(12)
    fns[0].mod = 2
    if not fn_in_lib(0) or not fn_dewy(0): exit(13)
    loop m in [3, 4]:
        fns[0].mod = i32(m)
        if fn_in_lib(0) or fn_dewy(0): exit(14)
    # Missing modules alone use the source-position fallback.
    loop m in [-1, 5]:
        fns[0].mod = i32(m)
        if not fn_in_lib(0) or not fn_dewy(0): exit(15)
        nodes[1].pos = mkpos(0, 3)
        if not fn_in_lib(0) or fn_dewy(0): exit(16)
        nodes[1].pos = 0
        if fn_in_lib(0) or fn_dewy(0): exit(17)
        nodes[1].pos = mkpos(2, 12)
    lib_root = ""
    if fn_in_lib(0) or not fn_dewy(0): exit(18)
    fns[0].mod = 0
    if fn_in_lib(0): exit(19)
    # Queries observe owner mutations, rather than caching old source context.
    files[0].is_dewy = true
    if not fn_dewy(0): exit(20)
    exact_marks = fill(u8(0), 8)
    nodes[1].pos = mkpos(1, 12)
    dir_name_runtime = 1; dir_name_prototype = 2
    loop mask in [0..256):
        exact_marks[1] = u8(mask)
        saved_marks = exact_marks
        loop flags in [0..16):
            fact_deferred_proving = flags & 1 != 0
            dir_obligations = flags & 2 != 0
            runtime = if flags & 4 != 0: 0 else: 1
            dir_scopes = [DirScope(mkpos(1, 0), mkpos(1, 100), 1, runtime)]
            dir_scopes_gen += 1
            exact_stores.clear(); exact_shader_owners.clear()
            if flags & 8 != 0: exact_shader_owners[0] = true
            expected = mask & 128 != 0 or (mask & 2 != 0 and mask & 8 == 0 and flags != 0)
            if fact_exact_demand(1) != expected: exit(21)
            if fact_exact_demand(-1) or fact_exact_demand(8): exit(22)
            if exact_marks != saved_marks: exit(23)
    # A mapped owner takes precedence over the absent-store default owner zero.
    exact_marks[1] = 2
    fact_deferred_proving = false; dir_obligations = false
    dir_scopes = [DirScope(mkpos(1, 0), mkpos(1, 100), 1, 1)]
    dir_scopes_gen += 1
    exact_stores[1] = 7
    if fact_exact_demand(1): exit(24)
    exact_shader_owners[7] = true
    if not fact_exact_demand(1): exit(25)
    print("function context and exact demand ok")
'''

BROADCAST = '''use 'main.jo'
use 'facts.jo'
use 'facts_values.dewy'
use 'facts_index_writes.dewy'
use 'facts_value_queries.dewy'
use 'refinement_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'exact.jo'
plain_ids = (values: int[]) -> int: values[0]
check_broadcast = (values: int[], want: int, captured: int):
    nodes = fill(Node(), 16)
    lists = [1]
    loop i in [0..values.len()):
        nodes[3+i] = Node(kind=.int_lit, type=i32(T_INT), ival=values[i])
        lists.push(i32(3+i))
    nodes[1] = Node(kind=.array, list=1, nlist=i32(values.len()))
    nodes[2] = Node(kind=.call, list=0, nlist=1)
    fact_terms = [FactTerm()]
    s = FactState(); saved = s
    value = fact_bcast_common(2, s)
    if plain_ids([value]) != value: exit(30)
    if want == -1:
        if value != 0: exit(31)
    else:
        b = fact_bound(s, value)
        if value == 0 or b.lo != want or b.hi != want: exit(32)
    if saved.ids.len() != 0 or saved.bounds.len() != 0 or saved.projections.len() != 0: exit(33)
    # One unit constant, then exactly the captured operands in source order.
    if fact_terms.len() != captured + 2: exit(34)
    loop i in [0..captured):
        if fact_terms[i+2].origin != i+3: exit(35)
main = ():
    init_types()
    exact_marks = []
    fact_query = false; fact_speculating = 0; fact_owner = 0
    check_broadcast([], 1, 0)
    check_broadcast([1, 1, 1], 1, 3)
    check_broadcast([1, 7, 1, 7], 7, 4)
    check_broadcast([0, 1, 0], 0, 3)
    check_broadcast([2, 3, 999], -1, 2)
    # Non-literal length arrays return unknown before constructing any state.
    nodes[1].kind = .ident
    s = FactState(); before = fact_terms.len()
    if fact_bcast_common(2, s) != 0 or fact_terms.len() != before or s.ids.len() != 0: exit(36)
    print("broadcast construction ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_facts_lifecycle_context_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAVES)
    compare_leaf(compiler, tmp_path, release, CONTEXT, extra_stems=LEAVES, jo_doubles=modules)


@pytest.mark.parametrize('release', [False, True])
def test_facts_values_broadcast_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAVES)
    compare_leaf(compiler, tmp_path, release, BROADCAST, extra_stems=LEAVES, jo_doubles=modules)


def test_facts_context_program_twins(compiler, tmp_path, monkeypatch):
    globs = ('broadcast_facts/*.dewy', 'broadcast_places/*.dewy', 'exact_int/*.dewy',
             'parallel_range_bound/*.dewy', 'nd_contracts/*.dewy', 'directive/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for pattern in globs for p in (ROOT / 'tests/cases').glob(pattern)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAVES) > 25
