"""Observing exact arithmetic does not narrow it to an operand's int64 type."""

import pytest

from tools.compiler import dewy_fuzz_programs as g


def test_exact_results_can_be_printed_interpolated_and_stringified():
    minimum = g.Lit(g.I, -(2 ** 63))
    negated = g.Unary(g.I, '-', minimum)
    program = g.Program((), (
        g.Print(negated),
        g.Print(g.Interp(g.S, ('<', negated, '>'))),
        g.Print(g.Conv(g.S, negated)),
    ))
    assert program.outcome() == (
        '9223372036854775808\n<9223372036854775808>\n9223372036854775808\n', 0)


def test_exact_result_still_checks_when_stored_as_int64():
    negated = g.Unary(g.I, '-', g.Lit(g.I, -(2 ** 63)))
    program = g.Program((), (g.Print(negated), g.Let('n', g.I, negated)))
    assert program.outcome() == ('9223372036854775808\n', 101)


@pytest.mark.parametrize(('seed', 'exit_code', 'observed'), (
    (2688088, 101, '<9223372036854775808>\n'),
    (2688142, 0, '= -9223372036854775817\n'),
    (2688150, 101, '-1948668849774537224271579776942746195725925395094\n'),
    (2688174, 0, '-207525870829232455680\n'),
))
def test_round8_overflow_replays(seed, exit_code, observed):
    program, _ = g.generate(seed)
    output, status = program.outcome()
    assert status == exit_code
    assert observed in output
