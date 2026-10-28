"""Unannotated multi-value arrays preserve exact arithmetic elements."""

from tools.compiler import dewy_fuzz_programs as g


def test_multi_collector_keeps_wide_int_before_printing():
    wide = g.Bin(g.I, '<<', g.Lit(g.I, -5), g.Lit(g.I, 62))
    values = g.MultiLit(g.AI, (
        wide,
        g.MultiBlock(g.MULTI, (g.Lit(g.I, 3),)),
        g.MultiIf(g.MULTI, g.Lit(g.B, True), (g.Lit(g.I, 4),), ()),
    ))
    program = g.Program((), (g.Print(values),))
    assert program.outcome() == ('[-23058430092136939520 3 4]\n', 0)


def test_seed_2689964_continues_after_wide_collector():
    program, _ = g.generate(2689964)
    output, status = program.outcome()
    assert status == 0
    assert '= [-24758800785707605497982484480 0 1 -175921860444160]\n' in output
