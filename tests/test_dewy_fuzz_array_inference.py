from tools.compiler import dewy_fuzz_programs as g


def test_exact_product_selects_math_int_unless_array_has_a_destination():
    maximum = g.Lit(g.I, 2**63 - 1)
    product = g.Bin(g.I, '*', maximum, g.Lit(g.I, 2))
    values = g.ArrayLit(g.AI, (product, maximum))
    program = g.Program((), (g.Print(values), g.Let('xs', g.AI, values)))
    assert program.outcome() == ('[18446744073709551614 9223372036854775807]\n', 101)


def test_optional_fallback_selects_the_collector_element_width():
    optional = g.Var(g.OI, 'x')
    one = g.Lit(g.I, 1)
    wide = g.Bin(g.I, '<<', g.Lit(g.I, 2), g.Lit(g.I, 63))
    block = g.MultiBlock(g.MULTI, (wide,))

    def outcome(fallback):
        array = g.MultiLit(g.AI, (g.Bin(g.I, '??', optional, fallback), block))
        return g.Program((), (g.Let('x', g.OI, one), g.Print(array))).outcome()

    assert outcome(one) == ('', 101)
    assert outcome(wide) == ('[1 18446744073709551616]\n', 0)
