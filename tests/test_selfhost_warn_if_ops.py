"""Soft preconditions: reading conditions, calls and type verdicts match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'refinement_types.dewy'
const T_INT = 1
const T_TEXT = 2
const T_OPT = 3
const T_VAR = 4
const T_AB = 5
const T_BC = 6
const T_A = 7
const T_B = 8
const T_C = 9
const T_ABC = 10
nodes: Node[] = [Node()]
lists: i32[]
fns: FnInst[] = [FnInst(), FnInst()]
ctxs: FnCtx[] = [FnCtx(), FnCtx(inst=12)]
cx = -1
types: TypeInfo[] = [TypeInfo(), TypeInfo(), TypeInfo(kind=.str_), TypeInfo(kind=.opt), TypeInfo(), TypeInfo(), TypeInfo(), TypeInfo(), TypeInfo(), TypeInfo(), TypeInfo()]
ut_paths_used = false
ut_p_name = 40
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
fatal = (pos: int, msg: str): print("fatal {pos}: {msg}")
warn = (pos: int, msg: str): print("warn {pos}: {msg}")
name_of = (n: int) -> str:
    if n == 1: return "warn_if"
    if n == 2: return "length"
    "name{n}"
pos_in_lib = (pos: int) -> bool: pos >= 1000
resolve_type = (n: int) -> int: 200 + n
subst = (t: int, targs: int[]) -> int:
    print("subst {t} {targs}")
    if t >= 200: t - 200 else: t
ntype = (n: int) -> int: int(nodes[n].type)
prune = (t: int) -> int: t
has_var = (t: int) -> bool: t == T_VAR
type_eq = (a: int, b: int) -> bool: a == b
is_union = (t: int) -> bool: t == T_AB or t == T_BC or t == T_ABC
union_members = (t: int) -> int[]:
    if t == T_AB: return [T_A, T_B]
    if t == T_BC: return [T_B, T_C]
    [T_A, T_B, T_C]
ut_names_safe = (n: int) -> bool: nodes[n].kind == .dotname
cx_token = (x: int) -> Tok: x as Tok
fact_comparison = (t: Tok) -> bool: t == .lt or t == .le or t == .gt or t == .ge or t == .eq or t == .ne
fact_inverse = (t: Tok) -> Tok:
    if t == .lt: return .ge
    if t == .ge: return .lt
    if t == .gt: return .le
    if t == .le: return .gt
    if t == .eq: return .ne
    .eq
'''

DRIVER = r'''
use 'warn_if.jo'
term = (k: NK, a: int, b: int, name: int, op: int) -> int:
    n = mk(k, nodes.len())
    nodes[n].a = i32(a); nodes[n].b = i32(b); nodes[n].name = i32(name); nodes[n].op = i32(op)
    n
ident = (name: int) -> int: term(.ident, 0, 0, name, 0)
lit = (v: int) -> int:
    n = mk(.int_lit, nodes.len())
    nodes[n].ival = v
    n
cmp = (op: Tok, a: int, b: int) -> int: term(.binary, a, b, 0, int(op))
kind_only = (k: NK) -> int: mk(k, nodes.len())
attr = (name: int, cond: int, msg: int) -> int: term(.dotname, cond, msg, name, 0)
text = (sval: int, aux: int) -> int:
    n = mk(.str_lit, 5)
    nodes[n].sval = i32(sval); nodes[n].aux = i32(aux)
    n
decl_of = (params: int[], attrs: int[]) -> int:
    d = mk(.fn_, 1)
    set_list(d, params)
    holder = mk(.block, 2)
    set_list(holder, attrs)
    nodes[d].c = i32(holder)
    d
tm = (t: RefTerm) -> str: "({t.kind} {t.value} {t.unsigned} {t.path} {t.offset})"
show = ():
    keys = wi_decls.keys()
    keys.sort()
    loop k in keys:
        loop w in wi_decls[k]:
            print("{k}: {w.kind} {w.param} {w.wrapped} {w.negated} {w.type} '{w.message}'")
            loop a in w.atoms: print("  {int(a.op)} {tm(a.a)} {tm(a.b)}")
    print("any {wi_any} paths {ut_paths_used}")
read_one = (params: int[], cond: int, sval: int):
    wi_read_decl(decl_of(params, [attr(1, cond, text(sval, 0))]))
call_at = (pos: int, args: int[]) -> int:
    n = mk(.call, pos)
    set_list(n, args)
    n
typed = (t: int) -> int:
    n = mk(.int_lit, 900)
    nodes[n].type = i32(t)
    n
facts = ():
    keys = wi_fact_calls.keys()
    keys.sort()
    loop k in keys: print("fact {k} {wi_fact_calls[k]} {wi_fact_targs[k]}")
    loop r in wi_fact_requests: print("request {r.node} {r.owner}")
main = ():
    # Declarations: none attached, other attributes, every malformed attribute, then one read once.
    wi_read_decl(mk(.fn_, 1))
    px = ident(30)
    py = ident(31)
    params = [px, py]
    wi_read_decl(decl_of(params, [attr(2, 0, 0)]))
    show()
    good_msg = text(50, 0)
    x = ident(30)
    y = ident(31)
    loop bad in [attr(1, 0, good_msg), attr(1, cmp(.lt, x, y), 0), attr(1, cmp(.lt, x, y), kind_only(.int_lit)), attr(1, cmp(.lt, x, y), text(51, 1))]:
        wi_read_decl(decl_of(params, [bad]))
    wi_reset()
    d = decl_of(params, [attr(2, 0, 0), attr(1, cmp(.lt, x, y), good_msg), attr(1, cmp(.ge, x, lit(3)), text(52, 0))])
    wi_read_decl(d)
    wi_read_decl(d)
    show()
    # Parameters, terms, and every shape of condition.
    print("{wi_param(d, ident(31))} {wi_param(d, ident(32))} {wi_param(d, lit(1))} {wi_param(d, ident(30))}")
    length = term(.field, x, 0, 2, 0)
    wi_reset()
    loop c in [cmp(.gt, length, lit(10)), cmp(.ge, y, term(.unary, lit(4), 0, 0, int(Tok.minus))), cmp(.eq, x, y), cmp(.ne, x, lit(0)), cmp(.le, x, y),
               term(.or_, cmp(.lt, x, lit(1)), cmp(.gt, y, lit(2)), 0, 0),
               term(.not_, term(.and_, cmp(.lt, x, lit(1)), term(.not_, cmp(.gt, y, lit(2)), 0, 0, 0), 0, 0), 0, 0, 0),
               term(.not_, cmp(.eq, x, length), 0, 0, 0)]:
        read_one(params, c, 60)
    show()
    # Unsupported conditions: each report, and what the fatal path would still build.
    wi_reset()
    loop c in [cmp(.lt, ident(33), lit(1)), cmp(.lt, term(.unary, ident(30), 0, 0, int(Tok.minus)), lit(1)), cmp(.lt, term(.unary, lit(4), 0, 0, int(Tok.plus)), lit(1)),
               cmp(.lt, term(.field, ident(33), 0, 2, 0), lit(1)), cmp(.lt, term(.field, x, 0, 3, 0), lit(1)), term(.and_, x, y, 0, 0), term(.not_, term(.or_, x, y, 0, 0), 0, 0, 0),
               term(.binary, x, y, 0, int(Tok.plus)), term(.not_, term(.binary, x, y, 0, int(Tok.plus)), 0, 0, 0), lit(7)]:
        read_one(params, c, 61)
    show()
    # Type tests and the path brand.
    wi_reset()
    safe = kind_only(.dotname)
    plain = kind_only(.ident)
    wrap = term(.call, ident(40), 0, 0, 0)
    set_list(wrap, [y])
    other_call = term(.call, ident(41), 0, 0, 0)
    set_list(other_call, [y])
    no_callee = term(.call, 0, 0, 0, 0)
    set_list(no_callee, [y])
    two = term(.call, ident(40), 0, 0, 0)
    set_list(two, [y, x])
    loop subject in [x, wrap, other_call, no_callee, two, kind_only(.int_lit)]:
        read_one(params, term(.not_, term(.istype, subject, safe, 0, 0), 0, 0, 0), 62)
        read_one(params, term(.istype, subject, safe, 0, 0), 63)
        read_one(params, term(.istype, subject, plain, 0, 0), 64)
        read_one(params, term(.not_, term(.istype, subject, plain, 0, 0), 0, 0, 0), 65)
    show()
    # A call: from a library, of an undeclared function, then each kind of condition.
    wi_reset()
    wa = decl_of(params, [attr(1, term(.not_, term(.istype, x, plain, 0, 0), 0, 0, 0), text(70, 0))])
    wi_decls[wa] = [WarnIf(WI_TYPE, 0, false, true, atoms=[], message="t not"), WarnIf(WI_TYPE, 1, false, false, T_AB, [], "t is")]
    wp = decl_of(params, [])
    wi_decls[wp] = [WarnIf(WI_PATH, 0, atoms=[], message="p")]
    wf = decl_of(params, [])
    wi_decls[wf] = [WarnIf(WI_FACTS, atoms=[], message="f"), WarnIf(WI_FACTS, atoms=[], message="g")]
    fns[1].targs = [7, 8]
    wi_call(call_at(1000, []), 1, wa)
    wi_call(call_at(1, []), 1, 77777)
    show()
    wi_call(call_at(2, []), 1, wp)
    show()
    c1 = call_at(3, [])
    wi_call(c1, 1, wf)
    wi_call(c1, 1, wf)
    cx = 1
    wi_call(call_at(4, []), 1, wf)
    cx = -1
    facts()
    wi_decls[wa][0].type = T_A
    wi_decls[wa][1].type = T_AB + 200
    wi_call(call_at(5, []), 1, wa)
    wi_call(call_at(6, [typed(T_A)]), 1, wa)
    loop a in [T_A, T_AB, T_C, T_ABC, T_BC, 0, T_VAR]:
        loop b in [T_A, T_AB, T_C, T_ABC]: wi_call(call_at(7 + a * 16 + b, [typed(a), typed(b)]), 1, wa)
    # The verdict itself over every pair, and the argument under its conversions.
    all = [0, T_INT, T_TEXT, T_OPT, T_VAR, T_AB, T_BC, T_A, T_B, T_C, T_ABC]
    loop a in all:
        row = ""
        loop t in all: row = "{row} {wi_is(a, t)}"
        print(row)
    conv = term(.conv, typed(T_A), 0, 0, 0)
    nodes[conv].type = i32(T_B)
    no_inner = term(.conv, 0, 0, 0, 0)
    nodes[no_inner].type = i32(T_C)
    wrapper = call_at(8, [typed(T_INT)])
    nodes[wrapper].aux = 3
    nodes[wrapper].type = i32(T_TEXT)
    other_aux = call_at(9, [typed(T_INT)])
    nodes[other_aux].aux = 2
    nodes[other_aux].type = i32(T_OPT)
    resolved = call_at(10, [typed(T_INT)])
    nodes[resolved].aux = 3; nodes[resolved].sym = 4
    nodes[resolved].type = i32(T_AB)
    pair = call_at(11, [typed(T_INT), typed(T_INT)])
    nodes[pair].aux = 3
    nodes[pair].type = i32(T_BC)
    chain = typed(T_A)
    loop i in [0..20):
        next = term(.conv, chain, 0, 0, 0)
        nodes[next].type = i32(T_C + i)
        chain = next
    print("{wi_arg_type(conv)} {wi_arg_type(no_inner)} {wi_arg_type(wrapper)} {wi_arg_type(other_aux)} {wi_arg_type(resolved)} {wi_arg_type(pair)} {wi_arg_type(chain)} {wi_arg_type(typed(T_B))}")
    wi_reset()
    show()
    print("{wi_fact_calls.len()} {wi_fact_targs.len()} {wi_fact_requests.len()}")
    print("warn_if ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_warn_if_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/warn_if.jo').read_text()
    state = state[state.index('const WI_TYPE'):state.index('# facts.jo: the call n')]
    output = compare_narrow(compiler, tmp_path, release,
                            ('checker_tokens', 'node_store', 'checker_types', 'checker_state', 'refinement_types', 'refine_predicates', 'warn_if_ops'), DRIVER,
                            doubles={'services.jo': SERVICES, 'warn_if.jo': "use 'services.jo'\nuse 'refinement_types.dewy'\n" + state},
                            services=('ast', 'check', 'checked_eval', 'expr', 'facts', 'safe_paths', 'types', 'util'))
    assert output.endswith(b'warn_if ok\n')
    for text in (b'unsupported `$warn_if` condition', b'a soft precondition takes', b'warn 900: t is', b"'name62'", b'name65'):
        assert text in output, text
