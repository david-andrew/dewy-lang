"""N-D selector contracts: axes, stepped ranges and slice obligations match frozen Jo."""
import pytest

from tests.selfhost_fact_double import FACT_SERVICES
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

STEMS = ('source_types', 'node_store', 'checker_types', 'checker_state', 'checker_tokens', 'refinement_types', 'nd_slices')
SERVICES = ('facts', 'nd_contracts', 'expr', 'witness', 'ast', 'types', 'refine')

DRIVER = r'''
s = FactState()
call = (kind: int, args: int[] = [], t: int = T_OTHER) -> int:
    nodes.push(Node(kind=.call, type=i32(t), pos=9))
    n = nodes.len() - 1
    node_set_list(mut nodes, mut lists, n, args)
    call_kinds[n] = kind
    n
typed = (t: int) -> int:
    nodes.push(Node(kind=.int_lit, type=i32(t)))
    nodes.len() - 1
c = (x: int) -> int: fact_constant(s, x)
wide = () -> int: fact_fresh(s, T_INT)
loose = () -> int: fact_new(s, FactBound(0, 9))
constructed = (n: int, actuals: int[]) -> int:
    v = fact_new(s, FactBound(), FactTerm(type=T_OTHER, origin=n))
    fact_constructor_actuals[v] = actuals
    v
show = (a: FactNDAxis): print("axis {a.first} {a.stop} {a.keep} {a.known} {a.count} {a.picks}")
range11 = (first: int, second: int, last: int, inclusive: int, bounded: int, stepped: int, exclusive: int) -> int[]:
    [c(first), c(second), c(last), c(inclusive), c(bounded), c(stepped), c(exclusive)]
range13 = (first: int, second: int, last: int, stepped: int, inclusive: int) -> int[]:
    [c(first), c(second), c(last), c(stepped), c(inclusive)]
axis = (value: int, extent: int = 0): show(fact_nd_axis(1, s, value, if extent == 0: c(100) else: extent))
stepped = (first: int, second: int, last: int, inclusive: int, bounded: int, tail: int):
    show(fact_nd_range(1, s, range11(first, second, last, inclusive, bounded, 1, tail), c(100), 11))
slice = (kind: int, rank: int, specs: int[]):
    print("== slice {kind} {rank} {specs}")
    shape = wide()
    spec = wide()
    array = shape
    if kind != 154:
        array = wide()
        fact_add_projection(s, FactProjection(array, -40, false, shape))
    fact_add_projection(s, FactProjection(shape, -1, false, c(rank)))
    fact_add_projection(s, FactProjection(spec, -1, false, c(specs.len())))
    loop i in [0..specs.len()): fact_add_projection(s, FactProjection(spec, indexed(i), true, specs[i]))
    loop i in [0..rank):
        if kind == 154: fact_add_projection(s, FactProjection(shape, indexed(i), true, c(10 + i)))
        else: fact_add_projection(s, FactProjection(array, -41 - indexed(i), false, c(10 + i)))
    n = call(kind, [source_kid(rank), typed(T_ARRAY_OF_INT)], T_OTHER)
    values = [array, spec]
    if kind == 152 or kind == 153: values.push(c(12))
    print(fact_nd_slice(n, s, values, kind))
indexed = (i: int) -> int: fact_constant(s, i)
# (the double names a source only at an odd node)
source_kid = (rank: int) -> int:
    k = typed(T_OTHER)
    if k % 2 != rank % 2: k = typed(T_OTHER)
    k
picks_of = (entries: int[], size: int) -> int:
    v = wide()
    inventories[v] = entries
    fact_add_projection(s, FactProjection(v, -1, false, c(size)))
    v
main = ():
    # Captures keep each actual reachable.
    print(fact_nd_remember(call(11), s, [c(1), 0, c(3)], 7))
    # Axes: no selector; no constructor; each kind of constructor.
    axis(0)
    axis(wide())
    nodes.push(Node(kind=.int_lit)); not_call = nodes.len() - 1
    axis(constructed(not_call, []))
    axis(constructed(call(99), []))
    axis(constructed(call(14), [c(100), c(0), c(1), c(5), c(0), c(1), c(0)]))
    axis(constructed(call(14), [c(1)]))
    axis(constructed(call(154), [c(1), c(2), c(1), c(3), c(4)]))
    axis(constructed(call(154), [c(1), c(2), c(0), c(3), c(4)]))
    axis(constructed(call(154), [c(1), c(2), loose(), c(3), c(4)]))
    axis(constructed(call(154), [c(1), c(2)]))
    loop kind in [12, 155]:
        axis(constructed(call(kind, [typed(T_INT)]), [c(7)]))
        axis(constructed(call(kind, [typed(T_ARRAY_OF_INT)]), [c(8)]))
        axis(constructed(call(kind, [typed(T_OTHER)]), [c(8)]))
        axis(constructed(call(kind, [typed(T_RANGE)]), [0]))
        axis(constructed(call(kind, [typed(T_INT)]), []))
    axis(constructed(call(11), range11(1, 0, 5, 0, 1, 0, 0)))
    axis(constructed(call(13), range13(1, 0, 5, 0, 1)))
    # Ranges: each endpoint knowledge and shape.
    show(fact_nd_range(1, s, [c(1)], c(100), 11))
    show(fact_nd_range(1, s, [c(1)], c(100), 13))
    show(fact_nd_range(1, s, [c(1), c(0), c(5), c(0), c(1), wide(), c(0)], c(100), 11))
    show(fact_nd_range(1, s, [c(1), c(0), c(5), c(0), c(1), loose(), c(0)], c(100), 11))
    show(fact_nd_range(1, s, range11(1, 0, 5, 0, 0, 0, 0), c(100), 11))
    show(fact_nd_range(1, s, range11(1, 0, 5, 1, 1, 0, 0), c(100), 11))
    show(fact_nd_range(1, s, range11(1, 0, 5, 0, 1, 0, 1), c(100), 11))
    show(fact_nd_range(1, s, [c(1), c(0), c(5), c(0), wide(), c(0), c(0)], c(100), 11))
    show(fact_nd_range(1, s, [c(1), c(0), c(5), wide(), c(1), c(0), c(0)], c(100), 11))
    show(fact_nd_range(1, s, range13(1, 0, 5, 0, 1), c(100), 13))
    show(fact_nd_range(1, s, range13(1, 0, 5, 0, 0), c(100), 13))
    # Stepped constants, including the widest signed spans.
    MIN = -9223372036854775807 - 1
    MAX = 9223372036854775807
    loop row in [[0, 2, 10, 0, 1, 0], [0, 2, 10, 1, 1, 0], [0, 2, 11, 0, 1, 0], [10, 8, 0, 0, 1, 0], [10, 8, 0, 1, 1, 0], [10, 7, 0, 1, 1, 0], [0, 2, 0, 0, 1, 0], [0, 2, 0, 1, 1, 0], [5, 5, 9, 0, 1, 0], [5, 7, 1, 0, 1, 0], [1, 5, 9, 0, 0, 0], [5, 1, 0, 0, 0, 0], [0, 2, 10, 0, 1, 1], [0, 3, 1, 0, 1, 1], [0, 2, 4, 1, 1, 1], [MIN, MAX, MAX, 1, 1, 0], [MAX, MIN, MIN, 1, 1, 0], [MIN, MIN + 1, MAX, 1, 1, 0], [MIN, MIN + 2, MAX, 1, 1, 0], [MAX, MAX - 1, MIN, 1, 1, 0], [MIN, MIN + 3, MAX, 0, 1, 1], [MAX, MAX - 2, MIN, 1, 1, 1], [MIN, MAX, MAX, 0, 1, 1]]:
        print(row); stepped(row[0], row[1], row[2], row[3], row[4], row[5])
    show(fact_nd_range(1, s, range13(0, 3, 12, 1, 1), c(100), 13))
    show(fact_nd_range(1, s, range13(0, 3, 12, 1, 0), c(100), 13))
    # Half-open up to an unknown, a minimum or a constant extent; each unknown part.
    show(fact_nd_range(1, s, range11(0, 2, 0, 0, 0, 1, 0), c(MIN), 11))
    show(fact_nd_range(1, s, range11(0, 2, 0, 0, 0, 1, 0), wide(), 11))
    show(fact_nd_range(1, s, [c(0), c(2), wide(), c(1), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_range(1, s, [c(0), c(2), c(5), wide(), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_range(1, s, [c(0), c(2), c(5), c(1), loose(), c(1), c(0)], c(100), 11))
    show(fact_nd_range(1, s, [c(0), c(2), c(5), c(1), c(1), c(1), wide()], c(100), 11))
    # Symbolic steps: ordered by a loose first and second, both ways.
    b1 = fact_new(s, FactBound(1, 2))
    show(fact_nd_range(1, s, [b1, b1, c(5), c(0), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_symbolic_step(1, s, [c(0), c(2), c(5), c(0), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_symbolic_step(1, s, [c(5), c(2), c(0), c(0), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_symbolic_step(1, s, [c(0), c(2), c(5), c(1), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_symbolic_step(1, s, [c(5), c(2), c(0), c(1), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_symbolic_step(1, s, [c(0), c(2), c(0), c(0), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_symbolic_step(1, s, [c(0), c(2), c(0), c(1), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_symbolic_step(1, s, [c(0), c(2), c(5), c(0), c(0), c(1), c(0)], wide(), 11))
    show(fact_nd_symbolic_step(1, s, [c(5), c(2), c(0), c(0), c(0), c(1), c(0)], wide(), 11))
    show(fact_nd_symbolic_step(1, s, [c(0), c(0), c(5), c(0), c(1), c(1), c(0)], c(100), 11))
    show(fact_nd_symbolic_step(1, s, [c(0), c(2), c(5), c(1), c(1)], c(100), 13))
    # Selector entries: a whole inventory, a copy, a hull, or nothing certain.
    print(fact_selector_entries(s, picks_of([c(1), c(2)], 2), c(2)))
    partial = picks_of([c(1)], 2)
    print(fact_selector_entries(s, partial, c(2)))
    fact_add_projection(s, FactProjection(partial, FACT_ELEMENT_VALUE, false, c(6)))
    print(fact_selector_entries(s, partial, c(2)))
    fact_add_projection(s, FactProjection(partial, FACT_ELEMENT_COPY, false, c(7)))
    print(fact_selector_entries(s, partial, c(2)))
    print(fact_selector_entries(s, picks_of([c(1)], 2), wide()))
    # Integer picks narrow within the host word.
    fact_nd_integer_picks(call(1), s, picks_of([c(1), c(2)], 2))
    fact_nd_integer_picks(call(1), s, picks_of([c(1)], 2))
    # Slices of each kind.
    whole = constructed(call(11), range11(1, 0, 4, 0, 1, 0, 0))
    one = constructed(call(12, [typed(T_INT)]), [c(3)])
    empty_range = constructed(call(11), range11(5, 0, 2, 0, 1, 0, 0))
    span_wide = constructed(call(11), [wide(), c(0), wide(), c(0), c(1), c(0), c(0)])
    known_count = constructed(call(11), range11(0, 2, 8, 0, 1, 1, 0))
    empty_count = constructed(call(11), range11(5, 7, 1, 0, 1, 1, 0))
    picks = constructed(call(12, [typed(T_ARRAY_OF_INT)]), [picks_of([c(1), c(2)], 2)])
    partial_picks = constructed(call(12, [typed(T_ARRAY_OF_INT)]), [picks_of([c(1)], 2)])
    unknown = wide()
    loop kind in [150, 151, 152, 153, 154]:
        slice(kind, 2, [whole, one])
        slice(kind, 3, [known_count, empty_range, picks])
        slice(kind, 1, [empty_count])
        slice(kind, 1, [span_wide])
        slice(kind, 1, [unknown])
        slice(kind, 1, [partial_picks])
        slice(kind, 0, [])
    slice(150, 33, [])
    slice(150, 1, [whole, one])
    needs_hold = false
    slice(150, 2, [whole, one])
    print("slices ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_nd_slices_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare_narrow(compiler, tmp_path, release, STEMS, DRIVER, doubles={'services.jo': FACT_SERVICES}, services=SERVICES)
    assert output.endswith(b'slices ok\n')
    for text in (b'slice selectors fit', b'selects only positions', b'index array contains only', b'last selected index is below',
                 b'start is at most its end', b'assigned data length equals', b'fits int64', b'.data.length matches', b'the sliced array'):
        assert text in output, text
