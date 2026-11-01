"""Coercion's no-op front (cq_settled), can_coerce's same-type head (cq_can_coerce) and the
literal leaf's word fast path match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_literals import DRIVER as LITERALS
from tests.test_selfhost_checker_resolve import compare

# (a Dewy file's literal reaches the host as the semantic integer)
HEAD = LITERALS.split('main = ():')[0].replace(
    'assert(nodes[n].type == i32(T_INT))',
    'assert(nodes[n].type == i32(T_INT) or nodes[n].type == i32(T_MATH_INT))') + r'''
typed = (k: NK, t: int, flags: int = 0) -> int:
    n = node(k)
    nodes[n].type = i32(t); nodes[n].flags = i32(flags)
    n
settled = (n: int, t: int): print("settled:{n}:{t}:{cq_settled(&nodes, &types, n, t)}")
cq_rest = (n: int, from: int, to: int) -> bool:
    events.push("can_coerce:{n}:{from}:{to}")
    to == T_INT
cq_rest_host = CheckerCoerceHost(cq_rest)
cq_rest_binding = checker_coerce_bind(&cq_rest_host)
# An int literal of a Jo file checked where t is wanted: its type, flags and the host's calls.
word = (value: int, t: int, u64: bool = false):
    n = node(.int_lit, 0, value)
    if u64: nodes[n].flags = i32(2097152)
    count = events.len()
    r = xl_check_int(n, t)
    print("word:{value}:{t}:{r}:{nodes[n].type}:{int(nodes[n].flags) & 256}:{events.len() - count}")
'''

DRIVER = HEAD + r'''
main = ():
    prepare()
    x = typed(.ident, T_INT)
    settled(x, 0)
    settled(x, T_INT)
    settled(x, T_I8)
    settled(x, T_BOOL)
    settled(typed(.ident, 0), T_INT)
    settled(typed(.ident, T_INT, 256), T_INT)
    settled(typed(.int_lit, T_INT), T_INT)
    settled(typed(.str_lit, T_STR), T_STR)
    settled(typed(.float_lit, T_FLOAT), T_FLOAT)
    settled(typed(.binary, T_FLOAT), T_FLOAT)
    # (type variables bound to the wanted type, on either side)
    v = int(tb_mk_var()); types[v].ref = i32(T_INT)
    settled(typed(.ident, v), T_INT)
    settled(x, v)
    free = int(tb_mk_var())
    settled(typed(.ident, free), T_INT)
    settled(typed(.ident, free), free)
    # (a refinement or a callable is checked or adapted by the host even when equal)
    types.push(TypeInfo(kind = .refined, elem = i32(T_INT)))
    refined = types.len() - 1
    settled(typed(.ident, refined), refined)
    types.push(TypeInfo(kind = .callable))
    callable = types.len() - 1
    settled(typed(.ident, callable), callable)
    # can_coerce: equal once pruned here, else the host's
    count = events.len()
    loop pair in [(T_INT, T_INT), (v, T_INT), (T_INT, v), (free, free), (T_I8, T_INT), (T_I8, T_BOOL), (free, T_INT)]:
        print("can_coerce:{pair.0}:{pair.1}:{cq_can_coerce(x, pair.0, pair.1)}")
    print("can_coerce hosts:{events.len() - count}")
    # Word literals: in range, retyped here; out of range, the host's to report.
    word(127, T_I8); word(128, T_I8); word(-128, T_I8); word(-129, T_I8)
    word(255, T_U8); word(256, T_U8); word(-1, T_U8); word(0, T_U8)
    word(65535, T_U16); word(-32768, T_I16); word(2147483647, T_I32); word(-2147483649, T_I32)
    word(4294967295, T_U32); word(4294967296, T_U32)
    word(-1, T_U64); word(9223372036854775807, T_U64); word(-5, T_INT)
    word(-1, T_U64, true); word(-1, T_INT, true); word(-1, T_U32, true)
    # (into the semantic integer, a float or nothing: the host's, as before)
    word(5, T_MATH_INT); word(5, T_FLOAT); word(5, 0)
    files[0].is_dewy = true
    word(5, T_I8)
    files[0].is_dewy = false
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_coerce_twins(compiler, tmp_path, release):  # noqa: F811
    out = compare(compiler, tmp_path, release, DRIVER, extra_stems=('checker_exact', 'checker_literals'))
    assert out.endswith(b'ok\n')
    for line in (b'settled:', b'word:127:', b'word:128:'):
        assert line in out


# A literal that does not fit reaches the host's coerce, which reports it.
@pytest.mark.parametrize('value,target,u64', [
    (128, 'T_I8', False),
    (-1, 'T_U8', False),
    (4294967296, 'T_U32', False),
    (-1, 'T_U32', True),
])
def test_checker_coerce_misfit_reported(compiler, tmp_path, value, target, u64):  # noqa: F811
    driver = HEAD.replace('literal_coerce = (n: int, t: int) -> int:\n',
                          'literal_coerce = (n: int, t: int) -> int:\n'
                          '    print("misfit:{nodes[n].ival}:{t}"); exit(17)\n') + f'''
main = ():
    prepare()
    word({value}, {target}, {'true' if u64 else 'false'})
    print("fit")
'''
    out = compare(compiler, tmp_path, False, driver, 17, extra_stems=('checker_exact', 'checker_literals'))
    assert out.startswith(b'misfit:')
