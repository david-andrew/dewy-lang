"""Literal checking and type publication preserve callback order and COW views."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
literal_effects = false
literal_exact = false
literal_last = 0
literal_grow = false
literal_snapshot: Node[]
literal_effect_grow = false
literal_coerce = (n: int, t: int) -> int:
    assert(nodes[n].type == i32(T_INT))
    events.push("coerce:{n}:{t}")
    if literal_grow:
        literal_grow = false
        literal_snapshot = nodes
        loop i in [0..128): nodes.push(Node()); types.push(TypeInfo()); lists.push(0)
        xl_check_scalar(node(.bool_lit), 0)
    nodes[n].type = i32(t)
    n
literal_effect = (n: int, expected: int) -> int:
    assert(nodes[n].type != 0 and int(nodes[n].flags) & 128 == 0)
    events.push("effect:{n}:{expected}:{nodes[n].type}")
    if literal_effect_grow:
        literal_effect_grow = false
        loop i in [0..128): nodes.push(Node()); types.push(TypeInfo())
        nodes[n].kind = .unary
    T_BOOL
literal_note = (n: int):
    assert(int(nodes[n].flags) & 128 != 0)
    events.push("exact:{n}:{nodes[n].type}")
    # Finishing must restore last_checked after a semantic callback reenters.
    literal_last = -99
literal_charlike = (n: int):
    events.push("char:{n}")
    nodes[n].kind = .int_lit
literal_check = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    xl_check_int(n, expected)
literal_finalize = (n: int) -> int:
    events.push("finalize:{n}")
    int(nodes[n].type)
literal_format = (n: int, pos: int):
    events.push("format:{n}:{pos}")
    loop i in [0..128): nodes.push(Node()); lists.push(0)
literal_warning = (n: int): events.push("warning:{n}")
literal_float_error = (n: int): print("float-error"); exit(22)
literal_host = CheckerLiteralHost(literal_coerce, literal_effect, literal_note, literal_charlike, literal_check, literal_finalize, literal_format, literal_warning, literal_float_error)
literal_input = CheckerLiteralInput(&nodes, &lists, &types, &files, &refine, &literal_effects, &literal_exact, &literal_last, &T_STR, &T_FLOAT, &T_BOOL, &T_NULL, &T_INT, &T_MATH_INT, &literal_host)
literal_binding = checker_literals_bind(&literal_input)
literal_exact_input = CheckerExactInput(&nodes, &lists, &types, &files, &T_INT, &T_U64, &T_MATH_INT)
literal_exact_binding = checker_exact_bind(&literal_exact_input)
main = ():
    prepare()
    assert(xl_expected(0) == 0)
    types.push(TypeInfo(kind = .refined, elem = i32(T_INT)))
    refined = types.len() - 1
    assert(xl_expected(refined) == T_INT)
    refine = false; assert(xl_expected(refined) == refined); refine = true
    n = node(.int_lit)
    literal_grow = true
    assert(xl_check_int(n, T_FLOAT) == T_FLOAT and nodes[n].type == i32(T_FLOAT))
    assert(literal_snapshot[n].type == i32(T_INT) and int(literal_snapshot[n].flags) & 128 == 0)
    assert(literal_last == n and int(nodes[n].flags) & 128 != 0)
    opt = int(tb_mk_opt(T_FLOAT))
    assert(xl_check_int(node(.int_lit), opt) == T_FLOAT)
    assert(xl_check_int(node(.int_lit), 0) == T_INT)
    # (a Dewy file's unexpected integer literal is the semantic integer)
    files[0].is_dewy = true
    n = node(.int_lit)
    assert(xl_check_int(n, 0) == T_MATH_INT and nodes[n].type == i32(T_MATH_INT) and int(nodes[n].flags) & 256 != 0)
    files[0].is_dewy = false
    assert(xl_check_int(node(.int_lit), refined) == T_INT)
    f = node(.float_lit); nodes[f].flags = 256
    assert(xl_check_scalar(f, T_FLOAT) == T_FLOAT and int(nodes[f].flags) & 256 == 0)
    f = node(.float_lit); nodes[f].flags = 256
    assert(xl_check_scalar(f, opt) == T_FLOAT and int(nodes[f].flags) & 256 == 0)
    f = node(.float_lit)
    assert(xl_check_scalar(f, 0) == T_FLOAT and int(nodes[f].flags) & 256 != 0)
    assert(xl_check_scalar(node(.bool_lit), T_INT) == T_BOOL)
    assert(xl_check_scalar(node(.none_lit), opt) == opt)
    inferred = int(xl_check_scalar(node(.none_lit), 0))
    assert(types[inferred].kind == .opt and types[int(types[inferred].elem)].kind == .var)
    ptr = int(tb_mk_ptr(T_INT))
    assert(xl_check_scalar(node(.null_lit), ptr) == ptr)
    assert(xl_check_scalar(node(.null_lit), 0) == T_NULL)
    assert(xl_check_str(node(.str_lit), 0) == T_STR)
    char = node(.str_lit); nodes[char].flags = 512
    assert(xl_check_str(char, T_INT) == T_INT and nodes[char].kind == .int_lit)
    first = node(.pair, node(.int_lit))
    second = node(.pair, node(.int_lit))
    text = node(.str_lit, 0, 0, 1, [first, node(.str_lit), second])
    count = events.len()
    assert(xl_check_str(text, 0) == T_STR)
    assert(events[count] == "warning:{nodes[first].a}" and events[count + 3] == "format:{first}:{nodes[first].pos}")
    assert(events[count + 4] == "warning:{nodes[second].a}")
    literal_effects = true; literal_effect_grow = true
    n = node(.ident)
    assert(xl_finish(n, refined, T_INT) == T_BOOL and nodes[n].type == i32(T_BOOL))
    assert(literal_last == n and nodes[n].kind == .unary)
    # (no expected type: callable inference has nothing to apply)
    n = node(.ident)
    count = events.len(); assert(xl_finish(n, T_INT, 0) == T_INT and events.len() == count)
    literal_effects = false
    # (int-to-float of an exact operation is noted; of anything else, not asked about)
    n = node(.conv); nodes[n].aux = 2
    count = events.len(); xl_finish(n, T_INT, 0); assert(events.len() == count and literal_last == n)
    src = node(.binary); nodes[src].type = i32(T_I32); nodes[src].op = 58
    n = node(.conv, src); nodes[n].aux = 2
    count = events.len(); xl_finish(n, T_INT, 0); assert(events.len() == count + 1 and literal_last == n)
    n = node(.conv)
    publication_snapshot = nodes
    count = events.len(); xl_finish(n, T_INT, 0); assert(events.len() == count)
    assert(publication_snapshot[n].type == 0 and publication_snapshot[n].flags == 0)
    assert(nodes[n].type == i32(T_INT) and int(nodes[n].flags) & 128 != 0)
    literal_exact = true
    n = node(.bool_lit); xl_finish(n, T_BOOL, 0); assert(literal_last == n)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_literals_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER,
                   extra_stems=('checker_exact', 'checker_literals')).endswith(b'ok\n')
