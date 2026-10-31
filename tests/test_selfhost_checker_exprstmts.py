"""Expression statements: checking, sinks, spawns and dropped-value warnings match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
fns: FnInst[] = [FnInst()]
sinks: Sink[]
es_repl_on = false
es_dropping = false
es_site = 0
es_hit = 0
es_last_at = 0
es_hit_next = false
es_rewrite = false
es_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{es_site}")
    if es_hit_next:
        es_hit_next = false
        es_hit = n
    es_last_at = n
    if es_rewrite:
        es_rewrite = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); fns.push(FnInst()); sinks.push(Sink())
        loop i in [0..256): sinks.pop()
        nodes.push(nodes[n])
        es_last_at = nodes.len() - 1
    int(nodes[n].type)
es_repl_host = (n: int):
    events.push("repl:{n}")
    nodes[n].kind = .int_lit
es_express_host = (s: int, t: int, pack: bool): events.push("express:{s}:{t}:{pack}")
es_result_host = (n: int, pos: int): events.push("unused-result:{n}:{pos}")
es_value_host = (code: int, op: int, a: int, pos: int, t: int): events.push("unused-value:{code}:{op}:{a}:{pos}:{t}")
es_spawn_host = (pos: int):
    print(events)
    print("error:{pos}:1")
    exit(19)
es_error_host = (n: int):
    print(events)
    print("error:{n}:2")
    exit(19)
es_services = CheckerExprStmtHost(es_check_host, es_repl_host, es_express_host, es_result_host, es_value_host, es_spawn_host, es_error_host)
es_inputs = CheckerExprStmtInput(&nodes, &types, &fns, &sinks, &es_repl_on, &es_dropping, &es_site, &es_hit, &es_last_at, &T_NEVER, &es_services)
es_bound = checker_exprstmts_bind(&es_inputs)
typed = (k: NK, t: int, a: int = 0) -> int:
    n = node(k, a); nodes[n].type = i32(t); n
stmt = (e: int) -> int: node(.exprstmt, e)
run = (s: int):
    es_statement(s)
    e = int(nodes[s].a)
    print("{s}:{e}:{int(nodes[e].kind)}:{int(nodes[e].flags)}:{es_site}:{es_hit}")
# A resolved call of function f (direct: callee 0) with one argument.
call_of = (f: int, t: int) -> int:
    c = node(.call, 0, 0, 0, [typed(.ident, t)]); nodes[c].type = i32(t); nodes[c].sym = i32(f); c
library_fn = (ret: int, params: int[], flags: int = 0) -> int:
    d = node(.fn_, 0, 0, 0, params); nodes[d].flags = i32(flags)
    fns.push(FnInst(decl = i32(d), ret = i32(ret), ptypes = params))
    fns.len() - 1
'''

MAIN = r'''
main = ():
    prepare()
    # Dropped values: kinds that change nothing, void and never, `_ =` (discarding).
    run(stmt(typed(.ident, T_INT)))
    b = typed(.binary, T_BOOL, typed(.ident, T_INT)); nodes[b].op = 69
    run(stmt(b))
    kinds: NK[] = [.and_, .or_, .not_, .bool_lit, .int_lit, .float_lit, .none_lit, .unary, .call]
    loop k in kinds: run(stmt(typed(k, T_INT)))
    run(stmt(typed(.ident, T_VOID)))
    run(stmt(typed(.ident, T_NEVER)))
    es_dropping = true
    run(stmt(typed(.int_lit, T_INT)))
    es_dropping = false
    # Checked already; matches become statements; the REPL's signature query.
    s = stmt(typed(.ident, T_INT)); nodes[s].flags = i32(128); run(s)
    run(stmt(typed(.match_, T_VOID)))
    es_repl_on = true
    run(stmt(typed(.ident, T_INT)))
    run(stmt(typed(.field, T_INT)))
    es_repl_on = false
    # Library results dropped: the host decides; void, never and narrow kinds do not ask.
    arr = int(tb_mk_array(T_INT))
    f = library_fn(arr, [arr])
    run(stmt(call_of(f, arr)))
    run(stmt(call_of(library_fn(T_INT, [T_INT]), T_INT)))
    run(stmt(call_of(library_fn(T_VOID, [arr]), T_VOID)))
    run(stmt(call_of(library_fn(arr, [arr], 4), arr)))
    run(stmt(call_of(library_fn(arr, [arr, arr]), arr)))
    run(stmt(call_of(library_fn(arr, []), arr)))
    c = call_of(f, arr); nodes[c].a = i32(typed(.ident, arr)); run(stmt(c))
    run(stmt(call_of(0, arr)))
    # Sinks: values expressed, packs, spawns; void and never values are not.
    sinks.push(Sink(mode = 1))
    es_hit_next = true
    run(stmt(typed(.ident, T_INT)))
    run(stmt(typed(.ident, T_VOID)))
    run(stmt(typed(.ident, T_NEVER)))
    sp = typed(.call, T_VOID); nodes[sp].aux2 = 17; run(stmt(sp))
    sp = typed(.call, T_INT); nodes[sp].aux2 = 17; run(stmt(sp))
    es_dropping = true
    run(stmt(typed(.ident, T_INT)))
    es_dropping = false
    sinks[0].mode = 0
    run(stmt(typed(.ident, T_INT)))
    sinks[0].mode = 4
    es_rewrite = true
    run(stmt(typed(.ident, T_STR)))
    es_dropping = true
    sp = typed(.call, T_INT); nodes[sp].aux2 = 17; run(stmt(sp))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_exprstmts_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_exprstmts',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('sinks.push(Sink(mode = 4)); sp = typed(.call, T_INT); nodes[sp].aux2 = 17; run(stmt(sp))', 1),
    ('run(stmt(typed(.ident, int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, false)))))', 2),
    ('run(stmt(typed(.field, int(tb_mk_cfn([T_INT], T_INT)))))', 2),
])
def test_checker_exprstmts_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=('checker_exprstmts',))
    assert output.rstrip().endswith(f':{code}'.encode())
