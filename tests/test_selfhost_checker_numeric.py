"""Numeric binaries: literal folding (wrapping, truncation, shifts), exact comparisons, joins."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xw_potential = false
xw_library = false
xw_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xw_potential_host = (n: int) -> bool:
    events.push("potential:{n}")
    xw_potential
xw_num_join_host = (a: int, b: int) -> int:
    events.push("num-join:{a}:{b}")
    0
xw_join_host = (a: int, b: int, pos: int) -> int:
    events.push("join:{a}:{b}")
    int(nodes[a].type)
xw_exact_host = (n: int) -> int:
    events.push("exact:{n}")
    T_MATH_INT
xw_library_host = (pos: int) -> bool: xw_library
xw_nan_host = (v: f64) -> f64:
    events.push("nan")
    v
xw_division_host = (n: int, x: int, y: int): events.push("division:{n}:{x}:{y}")
xw_percent_host = (n: int, a: int): events.push("percent:{n}:{a}")
xw_error_host = (n: int, code: int):
    print(events)
    print("error:{n}:{code}")
    exit(19)
xw_services = CheckerNumericHost(xw_coerce_host, xw_potential_host, xw_num_join_host, xw_join_host, xw_exact_host, xw_library_host, xw_nan_host, xw_division_host, xw_percent_host, xw_error_host)
xw_inputs = CheckerNumericInput(&nodes, &types, &files, &T_INT, &T_MATH_INT, &T_U64, &T_FLOAT, &T_BOOL, &T_NEVER, &xw_services)
xw_binding = checker_numeric_bind(&xw_inputs)
DEWY = 1 << 40
int_lit = (v: int, dewy: bool = false, flags: int = 256) -> int:
    n = node(.int_lit); nodes[n].ival = v; nodes[n].flags = i32(flags); nodes[n].type = i32(T_INT)
    if dewy: nodes[n].pos = DEWY + n
    n
float_lit = (v: f64) -> int:
    n = node(.float_lit); nodes[n].fval = v; nodes[n].flags = i32(256); nodes[n].type = i32(T_FLOAT); n
value = (t: int, k: NK = .ident, dewy: bool = false) -> int:
    n = node(k); nodes[n].type = i32(t)
    if dewy: nodes[n].pos = DEWY + n
    n
run = (op: Tok, a: int, b: int, dewy: bool = false, cmp: bool = false):
    n = node(.binary, a); nodes[n].b = i32(b); nodes[n].op = i32(int(op))
    if dewy: nodes[n].pos = DEWY + n
    t = xw_numeric(n, i32(int(op)), a, b, int(nodes[a].type), int(nodes[b].type), cmp)
    print("{n}:{t}:{int(nodes[n].kind)}:{nodes[n].ival}:{nodes[n].fval}:{nodes[n].type}:{int(nodes[n].flags)}:{nodes[a].type}:{nodes[b].type}:{int(nodes[a].flags)}")
prepare_numeric = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_numeric()
    low = -9223372036854775807 - 1
    ops: Tok[] = [.plus, .minus, .star, .slash, .percent, .amp, .pipe, .caret, .shl, .shr]
    pairs = [[7, 2], [-7, 2], [7, -2], [-7, -2], [0, 5], [low, -1], [9223372036854775807, 1], [1, 63], [3, 64], [-8, 70], [5, -1]]
    loop dewy in [false, true]:
        loop op in ops:
            loop p in pairs:
                if (op == .slash or op == .percent) and p[1] == -1 and p[0] == low: continue
                if (op == .shl or op == .shr) and (p[1] < 0 or (not dewy and p[1] >= 64)): continue
                if op == .slash and dewy: continue
                run(op, int_lit(p[0], dewy), int_lit(p[1], dewy), dewy)
    run(.shl, int_lit(1, true), int_lit(-1, true), false)
    run(.plus, int_lit(5, false, 256 | 2097152), int_lit(1), false)
    run(.plus, int_lit(-5, false, 256 | 2097152), int_lit(1), true)
    run(.minus, int_lit(-5, false, 256 | 2097152), int_lit(1), false)
    # Floats fold; NaN signs ask the host.
    run(.plus, float_lit(1.5), int_lit(2))
    run(.slash, int_lit(1), float_lit(4.0))
    run(.star, float_lit(0.0), float_lit(0.0))
    run(.slash, float_lit(0.0), float_lit(0.0))
    run(.percent, float_lit(1.0), float_lit(2.0))
    # Comparisons of exact values; widths; joins; bitwise; exact results.
    xw_potential = true
    run(.lt, int_lit(3), value(T_U32, .binary), false, true)
    run(.lt, value(T_INT, .binary), int_lit(3, false, 256 | 2097152), false, true)
    run(.lt, value(T_INT, .ident), int_lit(-3), false, true)
    xw_potential = false
    run(.eq, value(T_INT, .binary), value(T_INT, .unary), false, true)
    run(.lt, value(T_I32, .ident, true), value(T_U64, .ident, true), true, true)
    run(.plus, value(T_INT), value(T_INT), true)
    run(.plus, value(T_INT), value(T_INT))
    run(.plus, value(T_I32), value(T_INT), true)
    run(.plus, value(T_NEVER), value(T_NEVER), true)
    run(.amp, value(T_I8), value(T_I8))
    a = node(.binary, value(T_INT)); nodes[a].op = i32(int(Tok.slash)); nodes[a].type = i32(T_INT)
    run(.star, a, int_lit(100, false, 0))
    xw_library = true
    a = node(.binary, value(T_INT)); nodes[a].op = i32(int(Tok.slash)); nodes[a].type = i32(T_INT)
    run(.star, a, int_lit(100, false, 0))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_numeric_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_numeric',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(.slash, value(T_INT, .ident, true), value(T_INT), true)', 1),
    ('run(.shr, int_lit(1, true), int_lit(-1, true), true)', 2),
    ('run(.amp, value(T_FLOAT), value(T_FLOAT))', 3),
])
def test_checker_numeric_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_numeric()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=('checker_numeric',))
    assert output.rstrip().endswith(f':{code}'.encode())
