"""One-dimensional selection contracts: classification and obligations match frozen Jo."""
import pytest

from tests.selfhost_fact_double import FACT_SERVICES
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

STEMS = ('source_types', 'node_store', 'checker_types', 'checker_state', 'checker_tokens', 'refinement_types', 'nd_slices', 'sequence_selectors')
SERVICES = ('facts', 'nd_contracts', 'expr', 'witness', 'ast', 'types', 'refine', 'effects', 'ownership', 'util', 'check', 'effect_values', 'ownership_types')

EXTRA = r'''
ownership_decls: int[]
shareable = true
owned = false
effect_share = (t: int) -> bool: shareable
ownership_fact_type = (t: int) -> bool: owned
routes: {int: int[]} = {}
fact_receiver_route = (n: int, s: mut FactState) -> int[]:
    log("route {n}")
    [n]
fact_route_values = (s: mut FactState, route: int[]) -> int[]: routes.get(route[0]) ?? []
fact_change_route = (s: mut FactState, target: int, whole: bool, at: int, reason: FactReason):
    log("change {target} {whole} {at} {int(reason)}")
fact_store_route = (s: mut FactState, route: int[], value: int, at: int):
    log("store route {route} {value} {at}")
fact_path_call_effects = (n: int, s: mut FactState): log("call effects {n}")
'''

DRIVER = r'''
s = FactState()
typed = (t: int) -> int:
    nodes.push(Node(kind=.int_lit, type=i32(t)))
    nodes.len() - 1
call = (args: int[], t: int = T_ARRAY_OF_INT, kind: int = 0) -> int:
    nodes.push(Node(kind=.call, type=i32(t), pos=9))
    n = nodes.len() - 1
    node_set_list(mut nodes, mut lists, n, args)
    call_kinds[n] = kind
    n
c = (x: int) -> int: fact_constant(s, x)
wide = () -> int: fact_fresh(s, T_INT)
RANGES = "/lib/std/dewy_ranges.jo"
ARRAYS = "/lib/core/array.jo"
args_for = (count: int, a: int = T_ARRAY_OF_INT, b: int = T_INT, z: int = T_INT) -> int[]:
    out = [typed(a)]
    loop i in [1..count): out.push(typed(b))
    if count > 1: out[count - 1] = typed(z)
    out
classify = (n: int, kind: int): print("{kind}: {fact_sequence_classify(n, kind, if kind < 166: RANGES else: ARRAYS)}")
range_value = (first: int, stop: int) -> int:
    n = call([], T_OTHER, 11)
    nodes[n].kind = .call
    v = fact_new(s, FactBound(), FactTerm(type=T_OTHER, origin=n))
    fact_constructor_actuals[v] = [c(first), c(0), c(stop), c(0), c(1), c(0), c(0)]
    v
stepped = (first: int, second: int, last: int) -> int:
    n = call([], T_OTHER, 11)
    v = fact_new(s, FactBound(), FactTerm(type=T_OTHER, origin=n))
    fact_constructor_actuals[v] = [c(first), c(second), c(last), c(0), c(1), c(1), c(0)]
    v
picks_of = (entries: int[], size: int) -> int:
    v = wide()
    inventories[v] = entries
    fact_add_projection(s, FactProjection(v, -1, false, c(size)))
    v
select = (what: str, kind: int, values: int[], extra: int = 0):
    print("== {what} {kind}")
    n = call([typed(T_ARRAY_OF_INT), typed(if extra != 0: extra else: T_ARRAY_OF_INT), typed(T_ARRAY_OF_INT), typed(T_ARRAY_OF_INT)], T_ARRAY_OF_INT, kind)
    print(fact_sequence_select(n, s, values, kind))
main = ():
    print(fact_sequence_classify(call(args_for(2)), 160, ARRAYS))
    print(fact_sequence_classify(call(args_for(2)), 166, RANGES))
    # Each kind, its argument count and the types it takes.
    loop kind in [160, 163, 166, 169]:
        loop count in [1, 2, 3, 7, 8]: classify(call(args_for(count), T_ARRAY_OF_INT), kind)
    classify(call(args_for(7), T_ARRAY_OF_BOOL), 163)
    loop kind in [161, 164, 167, 170]:
        loop count in [2, 3, 8]:
            classify(call(args_for(count), T_OTHER), kind)
            classify(call(args_for(count, T_ARRAY_OF_INT, T_INT, T_ARRAY_OF_INT), T_OTHER), kind)
            classify(call(args_for(count, T_ARRAY_OF_INT, T_INT, T_OTHER), T_OTHER), kind)
    classify(call(args_for(2, T_OTHER)), 160)
    classify(call(args_for(2, T_FIXED)), 160)
    classify(call([typed(T_ARRAY_OF_INT), typed(T_ARRAY_OF_INT)]), 166)
    classify(call([typed(T_ARRAY_OF_INT), typed(T_ARRAY_OF_BOOL)]), 166)
    classify(call([typed(T_ARRAY_OF_INT), typed(T_OTHER)]), 166)
    classify(call([typed(T_ARRAY_OF_INT), typed(T_ARRAY_OF_BOOL)]), 169)
    classify(call([typed(T_ARRAY_OF_INT), typed(T_ARRAY_OF_INT)]), 169)
    classify(call([typed(T_ARRAY_OF_INT), typed(T_OTHER)]), 169)
    literal_off = args_for(8)
    nodes[literal_off[6]].kind = .bool_lit
    classify(call(literal_off, T_OTHER), 164)
    nodes[literal_off[6]].ival = 1
    classify(call(literal_off, T_OTHER), 164)
    shareable = false
    classify(call(args_for(2)), 160)
    shareable = true
    owned = true
    classify(call(args_for(2)), 160)
    ownership_decls = [1]
    classify(call(args_for(2)), 160)
    owned = false
    # Lengths: fixed arrays have one; others project it.
    print(fact_sequence_length(s, 5, T_FIXED))
    print(fact_sequence_length(s, 5, T_ARRAY_OF_INT))
    # Selecting: known axes, unknown axes, picks and masks; reads and stores.
    base = wide()
    fact_add_projection(s, FactProjection(base, -1, false, c(20)))
    loop kind in [160, 161, 162]:
        select("range", kind, [base, range_value(1, 5), wide(), wide()])
        select("reversed", kind, [base, range_value(5, 1), wide(), wide()])
        select("stepped", kind, [base, stepped(0, 2, 8), wide(), wide()])
        select("stepped empty", kind, [base, stepped(5, 7, 1), wide(), wide()])
        select("unknown", kind, [base, wide(), wide(), wide()])
    select("whole", 160, [base, 0])
    select("wide range", 160, [base, range_value(1, 5)])
    wider = wide()
    open_range = call([], T_OTHER, 11)
    v_open = fact_new(s, FactBound(), FactTerm(type=T_OTHER, origin=open_range))
    fact_constructor_actuals[v_open] = [wider, c(0), wide(), c(0), c(1), c(0), c(0)]
    select("symbolic", 160, [base, v_open])
    loop kind in [163, 164, 165]:
        select("literal", kind, [base, c(1), c(0), c(5), c(0), c(1), c(0), wide()])
    loop kind in [166, 167, 168]:
        select("picks", kind, [base, picks_of([c(1), c(2)], 2), wide()])
        select("short picks", kind, [base, picks_of([c(1)], 2), wide()])
    loop kind in [169, 170, 171]:
        select("mask", kind, [base, picks_of([c(0), c(1), c(1)], 3), wide()], T_ARRAY_OF_BOOL)
        select("unknown mask", kind, [base, picks_of([wide()], 1), wide()], T_ARRAY_OF_BOOL)
        select("short mask", kind, [base, picks_of([c(1)], 2), wide()], T_ARRAY_OF_BOOL)
    # A store's destination is reacquired: the held value decides the length.
    held = call([typed(T_ARRAY_OF_INT), typed(T_ARRAY_OF_INT)], T_ARRAY_OF_INT, 161)
    routes[held] = [wide(), base]
    print(fact_sequence_select(held, s, [wide(), range_value(1, 5), wide()], 161))
    # Stores: no held value, an address and conversions over the target, and a full projection table.
    plain = call([typed(T_ARRAY_OF_INT)], T_ARRAY_OF_INT, 161)
    fact_sequence_store(plain, s, 3, .write)
    routes[plain] = [base]
    fact_sequence_store(plain, s, 3, .write)
    inner = typed(T_ARRAY_OF_INT)
    nodes.push(Node(kind=.addr, a=i32(inner), type=i32(T_ARRAY_OF_INT))); addr = nodes.len() - 1
    nodes.push(Node(kind=.conv, a=i32(addr), type=i32(T_ARRAY_OF_INT))); wrapped = nodes.len() - 1
    target = call([wrapped], T_ARRAY_OF_INT, 161)
    routes[target] = [base]
    fact_sequence_store(target, s, 4, .write)
    loop s.projections.len() < FACT_CAP: s.projections.push(FactProjection(0, 0, false, 0))
    fact_sequence_store(target, s, 4, .write)
    select("full table", 160, [base, range_value(1, 5)])
    select("full table store", 161, [base, range_value(1, 5), wide()])
    loop kind in [160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172]:
        print("{kind}: {fact_sequence_store_call(call([], T_OTHER, kind))}")
    print("sequence ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_sequence_selectors_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare_narrow(compiler, tmp_path, release, STEMS, DRIVER, doubles={'services.jo': FACT_SERVICES + EXTRA}, services=SERVICES)
    assert output.endswith(b'sequence ok\n')
    for text in (b'range selects only positions', b'range first selected index', b'range last selected', b'range start is at most',
                 b'index array contains only', b'selected index is below', b'mask length equals', b'replacement length equals'):
        assert text in output, text
