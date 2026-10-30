"""Unary hints, literal folding, overloads and reentrant arenas match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xu_seen = 0
xu_bigint = false
xu_simple = false
xu_overload = 0
xu_nested = 0
xu_snapshot: Node[]
xu_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xu_nested != 0:
        inner = xu_nested; xu_nested = 0
        xu_snapshot = nodes
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); files.push(SrcFile())
        r = xu_check(inner, 0, 0)
        events.push("nested:{r.type}:{r.bypass}")
    xu_seen = n
    int(nodes[n].type)
xu_dotted_host = (n: int, expected: int) -> int:
    events.push("dotted:{n}:{expected}")
    T_STR
xu_bigint_host = (t: int) -> bool:
    events.push("bigint:{t}")
    xu_bigint
xu_simple_host = (t: int) -> bool:
    events.push("simple:{t}")
    xu_simple
xu_secret_host = (n: int) -> int:
    events.push("secret:{n}")
    T_BOOL
xu_quantity_host = (n: int, expected: int, literal: bool) -> int:
    events.push("quantity:{n}:{expected}:{literal}")
    T_FLOAT
xu_overload_host = (n: int) -> int:
    events.push("overload:{n}")
    xu_seen = -1
    xu_overload
xu_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xu_exact_host = (n: int) -> int:
    events.push("exact:{n}:{nodes[n].type}")
    T_MATH_INT
xu_error_host = (n: int, t: int, code: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
xu_services = CheckerUnaryHost(xu_check_host, xu_dotted_host, xu_bigint_host, xu_simple_host, xu_secret_host, xu_quantity_host, xu_overload_host, xu_coerce_host, xu_exact_host, xu_error_host)
xu_inputs = CheckerUnaryInput(&nodes, &types, &files, &xu_seen, &T_INT, &T_MATH_INT, &xu_services)
xu_binding = checker_unary_bind(&xu_inputs)
DEWY = 1 << 40
operand = (t: int, dewy: bool = false) -> int:
    n = node(.ident); nodes[n].type = i32(t)
    if dewy: nodes[n].pos = DEWY + n
    n
literal = (k: NK, t: int, dewy: bool = false) -> int:
    n = node(k); nodes[n].type = i32(t); nodes[n].flags = i32(256)
    if dewy: nodes[n].pos = DEWY + n
    n
unary = (op: Tok, a: int, dewy: bool = false) -> int:
    n = node(.unary, a); nodes[n].op = i32(int(op))
    if dewy: nodes[n].pos = DEWY + n
    n
show = (n: int, r: CheckerUnaryResult):
    print("{n}:{r.type}:{r.bypass}:{int(nodes[n].kind)}:{nodes[n].flags}:{nodes[n].type}:{nodes[n].a}:{nodes[n].ival}:{nodes[n].fval}:{xu_seen}")
run = (n: int, expected: int = 0, ex: int = 0):
    show(n, xu_check(n, expected, ex))
prepare_unary = () -> int:
    prepare()
    files.push(SrcFile(is_dewy = true))
    types.push(TypeInfo(kind = .quantity))
    q = types.len() - 1
    types.push(TypeInfo(kind = .secret))
    q
'''

MAIN = r'''
main = ():
    q = prepare_unary()
    secret = q + 1
    record = int(tb_mk_tuple([T_INT, T_STR]))
    types.push(TypeInfo(kind = .enum_))
    enum_type = types.len() - 1
    types.push(TypeInfo(kind = .struct_))
    struct_type = types.len() - 1
    # Broadcast forms leave through their owner before any operand work.
    b = unary(.minus, operand(T_INT)); nodes[b].flags = i32(16384)
    run(b, T_FLOAT, T_FLOAT)
    # Hints: numbers and vectors directly; records only as bundled big integers.
    loop ex in [T_INT, T_FLOAT, T_STR, struct_type, record]:
        run(unary(.minus, operand(T_INT)), ex, ex)
    xu_bigint = true
    run(unary(.minus, operand(T_INT)), struct_type, struct_type)
    xu_bigint = false
    # Quantity literals are syntactic: unchecked number times name under prefixes.
    times = node(.binary, literal(.int_lit, T_INT)); nodes[times].b = i32(operand(T_INT)); nodes[times].op = i32(int(Tok.star)); nodes[times].type = i32(q)
    run(unary(.minus, times), 7, 0)
    plus = unary(.plus, times); nodes[plus].type = i32(q)
    run(unary(.minus, plus), 0, 0)
    nodes[times].flags = i32(128)
    run(unary(.minus, times), 0, 0)
    slash = node(.binary, literal(.float_lit, T_FLOAT)); nodes[slash].b = i32(operand(T_INT)); nodes[slash].op = i32(int(Tok.slash)); nodes[slash].type = i32(q)
    run(unary(.minus, slash), 0, 0)
    run(unary(.tilde, operand(secret)), 0, 0)
    # Overloads for records, tuples and nonsimple enums.
    xu_overload = T_FLOAT
    loop t in [record, struct_type, enum_type]: run(unary(.minus, operand(t)), 0, 0)
    xu_simple = true
    xu_overload = 0
    run(unary(.minus, operand(T_FLOAT)), 0, 0)
    # Literal folding keeps the literal's type and drops everything else.
    lit = literal(.int_lit, T_INT); nodes[lit].ival = 42; nodes[lit].b = 9
    n = unary(.minus, lit); nodes[n].c = 3; nodes[n].sym = 4
    run(n)
    lit = literal(.float_lit, T_FLOAT); nodes[lit].fval = 2.5
    run(unary(.minus, lit))
    low = -9223372036854775807 - 1
    lit = literal(.int_lit, T_MATH_INT, true); nodes[lit].ival = low
    run(unary(.minus, lit, true))
    lit = literal(.int_lit, T_U64, true); nodes[lit].ival = low; nodes[lit].flags = i32(256 | 2097152)
    run(unary(.minus, lit, true))
    lit = literal(.int_lit, T_INT, true); nodes[lit].ival = 5
    run(unary(.minus, lit, true))
    inner = unary(.plus, literal(.int_lit, T_INT)); nodes[inner].flags = i32(256); nodes[inner].type = i32(T_INT)
    run(unary(.minus, inner))
    # Exact results for semantic integer negation in Dewy only.
    run(unary(.minus, operand(T_INT, true), true))
    run(unary(.minus, operand(T_INT)))
    run(unary(.minus, operand(T_I32, true), true))
    run(unary(.tilde, operand(T_INT, true), true))
    run(unary(.plus, operand(T_FLOAT, true), true))
    # A nested check grows every arena before the outer node is rewritten.
    xu_nested = unary(.minus, literal(.int_lit, T_INT))
    lit = literal(.int_lit, T_INT); nodes[lit].ival = 11
    n = unary(.minus, lit)
    run(n)
    assert(xu_snapshot.len() < nodes.len() and nodes[n].kind == .int_lit and nodes[n].ival == -11)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_unary_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_unary',)).endswith(b'ok\n')


@pytest.mark.parametrize('case', [
    'unary(.minus, operand(T_STR))',
    'unary(.tilde, operand(T_FLOAT))',
    'unary(.plus, operand(T_BOOL))',
    'unary(.minus, operand(enum_type))',
])
def test_checker_unary_errors(compiler, tmp_path, case):  # noqa: F811
    main = f'''
main = ():
    prepare_unary()
    types.push(TypeInfo(kind = .enum_))
    enum_type = types.len() - 1
    xu_simple = true
    xu_check({case}, 0, 0)
    print("unreachable")
'''
    assert b'error:' in compare(compiler, tmp_path, False, DRIVER + main, status=19,
                                extra_stems=('checker_unary',))
