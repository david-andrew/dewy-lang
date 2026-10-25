"""Oracle and generator fixes from the main fuzzer (tools/compiler/dewy_fuzz_programs.py)."""
from tools.compiler import dewy_fuzz_programs as gen

DICT_II = gen.Ty('dict', (gen.I, gen.I))
RANGE = gen.Range(gen.Ty('array', (gen.I,)), gen.Lit(gen.I, 1), gen.Lit(gen.I, 2), gen.Lit(gen.I, 3), True)


def comp(ty, value, key=None):
    return gen.Comp(ty, ('i1',), RANGE, None, value, key)


def times_max(name='i1'):
    return gen.Bin(gen.I, '*', gen.Var(gen.I, name), gen.Lit(gen.I, 2 ** 63 - 1))


def test_comprehension_elements_are_stored_checked():
    # Seed 7000118: the compiler panics storing an exact result past int64 into the element type.
    i1 = gen.Var(gen.I, 'i1')
    cases = [comp(gen.Ty('array', (gen.I,)), times_max()),
             comp(gen.Ty('set', (gen.I,)), times_max()),
             comp(DICT_II, times_max(), i1)]
    for c in cases:
        program = gen.Program((), (gen.Let('c', c.ty, c),))
        assert program.outcome() == ('', 101), c.render()


def test_comprehension_keys_are_stored_checked():
    c = comp(DICT_II, gen.Var(gen.I, 'i1'), times_max())
    assert gen.Program((), (gen.Let('c', DICT_II, c),)).outcome() == ('', 101)


def test_comprehension_in_range_still_runs():
    i1 = gen.Var(gen.I, 'i1')
    c = comp(DICT_II, i1, i1)
    program = gen.Program((), (gen.Let('c', DICT_II, c), gen.Print(gen.Var(DICT_II, 'c'))))
    assert program.outcome() == ('[1 -> 1 2 -> 2 3 -> 3]\n', 0)


def test_assertion_beyond_its_type_is_dropped():
    # Seed 7000644: `((uint64 + uint64) << 50) =? 4835703314487313717788672` cannot be written
    # as a uint64 literal, so the generator drops the assertion rather than emit it.
    big = gen.Bin(gen.U, '<<', gen.Lit(gen.U, 2 ** 32), gen.Lit(gen.U, 50))
    fits = gen.Bin(gen.U, '<<', gen.Lit(gen.U, 1), gen.Lit(gen.U, 3))
    filled = gen.fill_asserts(gen.Program((), (gen.Assert(1, big), gen.Assert(2, fits))))
    assert [s.tag for s in filled.body] == [2]
    assert filled.body[0].expected.value == 8
