"""Settled argument costs and candidate scoring preserve order, binds and failures."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVE, compare
from tests.selfhost_expr_double import jo_doubles

DRIVER = RESOLVE.split('main = ():')[0] + r'''
cost_context = (a: int) -> bool: nodes[a].aux == 2
cost_word = (t: int) -> bool: types[t].bits == 99
cost_grow = false
cost_fatal = false
cost_rest = (a: int, p: int, bs: mut int[]) -> int:
    events.push("cost:{a}:{p}:{bs}")
    if cost_fatal:
        print(events)
        exit(23)
    if bs.len() > 0: bs[0] += 1
    if cost_grow:
        cost_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo())
        rb: int[]
        assert(arg_cost(1, T_INT, rb) == 0)
    int(nodes[a].ival)
cost_mutable = (a: int, p: int, bs: mut int[], recv: mut bool, receiver: bool) -> int:
    events.push("mutable:{a}:{p}:{receiver}")
    if receiver and nodes[a].aux2 != -1: recv = true
    if bs.len() > 0: bs[0] += 10
    int(nodes[a].ival)
cost_node = (kind: NK, t: int, score: int = 4, literal: bool = false, context: bool = false) -> int:
    a = node(kind)
    nodes[a].type = i32(t); nodes[a].ival = score
    if literal: nodes[a].flags = 256
    if context: nodes[a].aux = 2
    a
score = (ns: int[], ps: int[], mask: int = 0):
    cd = Cand(args=ns, sig=FnSig(params=ps, mutmask=i32(mask)), binds=[0])
    recv = false
    failure = call_candidate_cost(cd, recv)
    print("score:{failure}:{cd.cost}:{cd.ok}:{cd.plain}:{recv}:{cd.binds}")
    print(events)
    events = []
main = ():
    prepare()
    events = []
    # Settled identity, including pruned aliases; no slow service or binding change.
    a = cost_node(.ident, T_INT)
    bs = [7]
    assert(arg_cost(a, T_INT, bs) == 0 and bs == [7])
    v = int(tb_mk_var()); types[v].ref = i32(T_INT)
    assert(arg_cost(a, v, bs) == 0)
    # Every exclusion from the settled head must reach the service.
    loop k in [TK.opt, TK.refined, TK.callable, TK.polyfn, TK.struct_]:
        t = types.len(); types.push(TypeInfo(kind=k, bits=99))
        x = cost_node(.ident, t)
        assert(arg_cost(x, t, bs) == 4)
    variable = int(tb_mk_var())
    x = cost_node(.ident, variable)
    assert(arg_cost(x, variable, bs) == 4)
    loop k in [NK.int_lit, NK.str_lit, NK.float_lit, NK.ident]:
        x = cost_node(k, T_INT, literal=k == .int_lit, context=k == .ident)
        assert(arg_cost(x, T_INT, bs) == 4)
    x = cost_node(.ident, 0)
    assert(arg_cost(x, T_INT, bs) == 4)
    assert(arg_cost(a, T_FLOAT, bs) == 4)
    print(events); events = []
    score([], [])
    score([a, 0, a], [T_INT, T_INT, T_INT])
    lit = cost_node(.int_lit, T_INT, 2, true)
    ctx = cost_node(.lambda, 0, 3, false, true)
    typed = cost_node(.ident, T_FLOAT, 1)
    # Written order differs from scoring order: typed, literal, context.
    cost_grow = true
    score([ctx, lit, typed], [T_INT, T_INT, T_INT])
    assert(not cost_grow)
    bad = cost_node(.ident, T_FLOAT, -1)
    score([lit, bad, ctx], [T_INT, T_INT, T_INT])
    score([bad, ctx], [T_INT, T_INT])
    score([typed, lit, ctx], [T_INT, T_INT, T_INT], 7)
    score([bad], [T_INT], 1)
    nodes[bad].aux2 = -1
    score([bad], [T_INT], 1)
    print("ok")
'''

DOUBLES = {
    'checker_call_queries': {
        'dewy': 'from p"expr.jo" import cc_context\nctx_dependent=(a:int64):>bool=>cc_context(a)\n',
        'jo': "use 'expr.jo'\nctx_dependent = (a: int) -> bool: cc_context(a)\n",
    },
}
JO = jo_doubles({name: {} for name in ('ast.jo', 'types.jo', 'units.jo')}, {
    'units.jo': {'bundled_word_rational_type': 'bundled_word_rational_type = (t: int) -> bool: cost_word(t)'},
    'expr.jo': {
        'ast': "use 'ast.jo'",
        'is_lit': 'is_lit = (n: int) -> bool: int(nodes[n].flags) & 256 != 0',
        'ntype': 'ntype = (n: int) -> int: int(nodes[n].type)',
        'cc_context': 'cc_context = (a: int) -> bool: cost_context(a)',
        'call_conversion_double': 'call_conversion_double = (a: int, p: int, bs: mut int[]) -> int: cost_rest(a, p, bs)',
        'call_mutable_double': 'call_mutable_double = (a: int, p: int, bs: mut int[], recv: mut bool, receiver: bool) -> int: cost_mutable(a, p, bs, recv, receiver)',
    },
})
# Empty Jo stand-ins still re-export the driver's arenas.
JO['ast.jo'] = "use 'node_store.dewy'\nnodes: Node[] = [Node()]\n"
JO['types.jo'] = "use 'checker_types.dewy'\ntypes: TypeInfo[] = [TypeInfo()]\nhas_var = (t: int) -> bool: int(types[t].flags) & 1 != 0\n"
DRIVER = ("use 'ast.jo'\nuse 'types.jo'\n" + DRIVER.replace('nodes: Node[] = [Node()]', '')
          .replace('types: TypeInfo[] = [TypeInfo()]', ''))

# A module boundary double isolates the scoring/resolver leaf from conversion.
JO['checker_call_convert.dewy'] = r'''from p"expr.jo" import call_conversion_double
arg_cost_rest=(a:int64 p:int64 @bs:array<int64>):>int64=>call_conversion_double(a p @bs)
'''
JO['checker_call_convert.jo'] = "use 'expr.jo'\narg_cost_rest = (a: int, p: int, bs: mut int[]) -> int: call_conversion_double(a, p, bs)\n"

JO['checker_call_convert.dewy'] += r'''from p"expr.jo" import call_mutable_double
call_mutable_cost=(a:int64 p:int64 @bs:array<int64> @recv:bool receiver:bool):>int64=>call_mutable_double(a p @bs @recv receiver)
'''
JO['checker_call_convert.jo'] += "call_mutable_cost = (a: int, p: int, bs: mut int[], recv: mut bool, receiver: bool) -> int: call_mutable_double(a, p, bs, recv, receiver)\n"


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_cost_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare(compiler, tmp_path, release, DRIVER, extra_stems=('checker_call_cost',),
                     doubles=DOUBLES, jo_doubles=JO)
    assert output.endswith(b'ok\n')
    assert b'score:2:0:false:false:false:[1]' in output
    assert b'score:-1:0:false:true:true:[10]' in output
    assert b'score:-1:0:false:true:false:[10]' in output


def test_checker_call_cost_error(compiler, tmp_path):  # noqa: F811
    driver = DRIVER.split('main = ():')[0] + '''main = ():
    prepare()
    events = []
    cost_fatal = true
    score([cost_node(.int_lit, T_INT, 0, true)], [T_INT])
'''
    compare(compiler, tmp_path, False, driver, status=23, extra_stems=('checker_call_cost',),
            doubles=DOUBLES, jo_doubles=JO)
