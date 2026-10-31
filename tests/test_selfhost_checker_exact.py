"""Exact arithmetic queries: exact_potential, exact_math_operand and exact_candidate match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
ex_input = CheckerExactInput(&nodes, &lists, &types, &files, &T_INT, &T_U64, &T_MATH_INT)
ex_binding = checker_exact_bind(&ex_input)
DEWY = 1 << 40
# A node of kind k typed t (op and aux as given), in a Dewy file or not.
mk = (k: NK, t: int, op: int = 0, aux: int = 0, dewy: bool = true, kids: int[] = []) -> int:
    n = node(k, 0, 0, aux, kids)
    nodes[n].type = i32(t); nodes[n].op = i32(op)
    if dewy: nodes[n].pos = DEWY + n
    n
wire = (n: int, a: int, b: int = 0, c: int = 0) -> int:
    nodes[n].a = i32(a); nodes[n].b = i32(b); nodes[n].c = i32(c); n
potential = (n: int): print("potential:{n}:{exact_potential(n)}")
operand = (n: int):
    before = nodes.len()
    w = exact_math_operand(n)
    print("operand:{n}:{w}:{nodes.len() - before}:{nodes[w].type}:{int(nodes[w].kind)}:{nodes[w].ival}")
'''

MAIN = r'''
main = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
    refined = types.len(); types.push(TypeInfo(kind = .refined, elem = i32(T_I32)))
    wide_refined = types.len(); types.push(TypeInfo(kind = .refined, elem = i32(T_INT)))
    policy = types.len(); types.push(TypeInfo(kind = .int_, bits = 32, sign = true, st = 1))
    secret = int(tb_mk_secret(T_I32))
    secret_refined = int(tb_mk_secret(refined))
    linked = int(tb_mk_var()); types[linked].ref = i32(T_U32)
    # Operations: + - * ** / << on exact types; the others, and other kinds, are not.
    loop op in [58, 59, 60, 79, 61, 67, 62, 63, 68, 69]:
        loop t in [T_INT, T_U64, T_I32, T_U32, T_MATH_INT, T_FLOAT, refined, wide_refined, policy, secret, secret_refined, linked, 0]:
            loop dewy in [true, false]: potential(mk(.binary, t, op, 0, dewy))
    potential(mk(.binary, T_INT, 58, 1))
    loop op in [59, 58, 77]: potential(mk(.unary, T_I32, op))
    loop aux in [89, 88]: potential(mk(.intrinsic, 0, 0, aux))
    potential(0)
    potential(-3)
    potential(mk(.int_lit, T_INT))
    # Values whose arms or operands are exact.
    yes = mk(.binary, T_INT, 58)
    no = mk(.ident, T_INT)
    loop op in [63, 64, 65, 58]:
        potential(wire(mk(.binary, T_INT, op, 2), no, yes))
        potential(wire(mk(.binary, T_INT, op, 2), no, no))
    loop aux in [0, 1, 2]: potential(wire(mk(.conv, T_MATH_INT, 0, aux), yes))
    loop k in [NK.if_, NK.iflet]:
        potential(wire(mk(k, T_INT), no, no, yes))
        potential(wire(mk(k, T_INT), no, yes, no))
        potential(wire(mk(k, T_INT), yes, no, no))
    potential(wire(mk(.coalesce, T_INT), no, yes))
    potential(wire(mk(.coalesce, T_INT), yes, no))
    arm_no = wire(mk(.arm, 0), yes, no)
    arm_yes = wire(mk(.arm, 0), no, yes)
    potential(mk(.match_, T_INT, 0, 0, true, [arm_no, arm_yes]))
    potential(mk(.match_, T_INT, 0, 0, true, [arm_no, arm_no]))
    potential(mk(.match_, T_INT, 0, 0, true, []))
    last_yes = wire(mk(.exprstmt, 0), yes)
    potential(mk(.block, T_INT, 0, 1, true, [arm_no, last_yes]))
    potential(mk(.block, T_INT, 0, 0, true, [arm_no, last_yes]))
    potential(mk(.block, T_INT, 0, 1, true, [last_yes, arm_no]))
    potential(last_yes)
    # The checked nodes exact.jo notes: operations, bitwise values over one, int-to-float.
    loop n in [mk(.binary, T_I32, 58), mk(.binary, T_INT, 69), wire(mk(.binary, T_INT, 63), no, yes), wire(mk(.binary, T_INT, 64), no, no), mk(.unary, T_I32, 59), mk(.unary, T_I32, 77), mk(.intrinsic, 0, 0, 89), wire(mk(.conv, T_FLOAT, 0, 2), yes), wire(mk(.conv, T_FLOAT, 0, 2), no), wire(mk(.conv, T_INT, 0, 1), yes), mk(.ident, T_INT)]:
        print("candidate:{n}:{exact_candidate(n)}")
    # Operands: an int's word computation behind its boundary.
    operand(mk(.ident, T_INT))
    operand(mk(.ident, T_MATH_INT))
    lit = mk(.int_lit, T_MATH_INT); nodes[lit].ival = 41
    operand(lit)
    big = mk(.int_lit, T_MATH_INT); nodes[big].ival = -5; nodes[big].flags = i32(2097152)
    operand(big)
    nodes[big].ival = 5
    operand(big)
    word = mk(.ident, T_INT)
    loop dewy in [true, false]: operand(wire(mk(.conv, T_MATH_INT, 0, 1, dewy), word))
    operand(wire(mk(.conv, T_MATH_INT, 0, 1), mk(.ident, T_I32)))
    operand(wire(mk(.conv, T_MATH_INT, 0, 2), word))
    # Reveal/wrap pairs peel while the child is still an int.
    inner = wire(mk(.conv, T_MATH_INT, 0, 1), word)
    operand(wire(mk(.conv, T_MATH_INT), wire(mk(.conv, T_MATH_INT), inner)))
    operand(wire(mk(.conv, T_MATH_INT), wire(mk(.conv, T_MATH_INT), lit)))
    operand(wire(mk(.conv, T_MATH_INT), word))
    operand(wire(mk(.conv, T_MATH_INT), wire(mk(.conv, wide_refined), word)))
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_exact_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=('checker_exact',))
    assert output.endswith(b'ok\n') and b'potential:' in output and b':true' in output
