"""Constant argument checks: declarations, constants, verdicts and narrowing match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'source_types.dewy'
use 'evaluator_state.dewy'
const NF_CHECKED = 128
const T_STR = 9
const T_UNION = 20
const T_NOT_UNION = 21
const T_ALL_FAIL = 22
const T_OPT = 30
const T_TEXT = 31
const T_NONE = 32
enum CV: none_, int_, int2float, float2int, float_, opt, ptr, bits, fn2clos, union_
nodes: Node[] = [Node()]
lists: i32[]
syms: Sym[] = [Sym()]
fns: FnInst[] = [FnInst(), FnInst(ret=33)]
ct_values: CTValue[] = [CTValue()]
next_value = 0
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
fatal = (pos: int, msg: str): print("fatal {pos}: {msg}")
pos_in_lib = (p: int) -> bool: false
cc_closed_expr = (x: int, depth: int) -> bool: nodes[x].kind == .int_lit
cc_fold_first = (n: int) -> int: 0
name_of = (n: int) -> str: if n == 1: "check_constant" else: "name{n}"
lookup = (n: int) -> int: if n < 50: n else: 0
wi_param = (decl: int, x: int) -> int: x - 100
get_fn_inst = (d: int, args: int[], pos: int) -> int:
    print("instance {d} {pos}")
    1
ct_run = (n: int) -> int:
    print("run sval={nodes[kid(n, 0)].sval} sym={nodes[n].sym} type={nodes[n].type} flags={nodes[n].flags}")
    next_value
checked_const_init = (k: int, sym: int, pos: int) -> int:
    print("const {k} {sym} {pos}")
    sym
binding_const_init = (k: SK, sym: int, pos: int) -> int: checked_const_init(int(k), sym, pos)
ntype = (n: int) -> int: int(nodes[n].type)
prune = (t: int) -> int: t
tkind = (t: int) -> TK:
    if t == T_OPT: return .opt
    if t == T_TEXT: return .str_
    .void_
is_union = (t: int) -> bool: t == T_UNION or t == T_ALL_FAIL or t == 23
union_members = (t: int) -> int[]:
    if t == T_ALL_FAIL: return [40, 41]
    if t == 23: return [50, 51, 40]
    [50, 40]
exception_member = (m: int) -> bool: m < 50
union_index = (t: int, m: int) -> int: 7
mk_union = (ms: int[]) -> int:
    print("union {ms}")
    60
'''

DRIVER = r'''
use 'check_constant.jo'
at = (name: int, call: int, msg: int, pos: int) -> int:
    n = mk(.dotname, pos)
    nodes[n].name = i32(name); nodes[n].a = i32(call); nodes[n].b = i32(msg)
    n
with = (attrs: int[]) -> int:
    d = mk(.fn_, 1)
    holder = mk(.block, 2)
    set_list(holder, attrs)
    nodes[d].c = i32(holder)
    d
str_lit = (text: int) -> int:
    n = mk(.str_lit, 3); nodes[n].sval = i32(text); n
ident = (name: int) -> int:
    n = mk(.ident, 4); nodes[n].name = i32(name); n
call_of = (callee: int, args: int[]) -> int:
    n = mk(.call, 5); nodes[n].a = i32(callee); set_list(n, args); n
sym_of = (k: int, s: int) -> int:
    n = mk(.ident, 6); nodes[n].aux = i32(k); nodes[n].sym = i32(s); n
show = ():
    keys = cc_decls.keys()
    keys.sort()
    loop k in keys: print("{k}: {cc_decls[k].len()} {cc_decls[k][0].params} {cc_decls[k][0].validator} {cc_decls[k][0].message}")
    print(cc_any)
main = ():
    syms = [Sym(), Sym(kind=.fns, decl=70), Sym(kind=.local, decl=71)]
    # Reading a declaration: every malformed spelling, then one that reads.
    cc_read_decl(mk(.fn_, 1))
    msg = str_lit(9)
    arg = mk(.int_lit, 7)
    while_100 = () -> int:
        loop nodes.len() <= 100: nodes.push(Node())
        nodes.len()
    while_100()
    p = mk(.int_lit, 8)
    other = at(2, 0, 0, 10)
    bad = [at(1, 0, msg, 11), at(1, call_of(ident(1), [p]), 0, 12), at(1, call_of(ident(1), [p]), mk(.int_lit, 13), 14),
           at(1, mk(.int_lit, 15), msg, 16), at(1, call_of(ident(1), []), msg, 17), at(1, call_of(mk(.int_lit, 18), [p]), msg, 19),
           at(1, call_of(ident(1), [arg]), msg, 20), at(1, call_of(ident(60), [p]), msg, 21), at(1, call_of(ident(2), [p]), msg, 22)]
    loop b in bad: cc_read_decl(with([other, b]))
    show()
    cc_reset()
    good = with([at(1, call_of(ident(1), [p]), msg, 23)])
    cc_read_decl(good)
    show()
    cc_read_decl(good)
    # Which arguments are constant strings.
    text = sym_of(1, str_lit(11))
    conv = mk(.conv, 24); nodes[conv].a = i32(str_lit(12)); nodes[nodes[conv].a].type = i32(T_STR)
    conv_other = mk(.conv, 25); nodes[conv_other].a = i32(mk(.int_lit, 26))
    conv_none = mk(.conv, 27)
    chain = str_lit(13); nodes[chain].type = i32(T_STR)
    loop i in [0..20):
        c = mk(.conv, 28); nodes[c].a = i32(chain); nodes[c].type = i32(T_STR); chain = c
    loop x in [str_lit(10), text, sym_of(2, str_lit(14)), sym_of(6, str_lit(15)), sym_of(3, str_lit(16)), sym_of(1, 0), sym_of(1, mk(.int_lit, 29)), conv, conv_other, conv_none, mk(.int_lit, 30), chain]:
        print(cc_constant(x))
    # A call: not checked, too few arguments, no constant, then each verdict and narrowing.
    print(cc_call(mk(.call, 31), 1, 999))
    print(cc_call(mk(.call, 32), 1, good))
    plain = (t: int) -> int:
        n = mk(.call, 33); nodes[n].type = i32(t)
        text = str_lit(35)
        nodes[text].type = i32(T_STR)
        set_list(n, [mk(.int_lit, 34), text])
        n
    cc_decls[good] = [CheckConstant([1], 70, "bad pattern")]
    na = mk(.call, 34); set_list(na, [mk(.int_lit, 35), mk(.int_lit, 36)])
    print(cc_call(na, 1, good))
    verdict = (t: int, i: int, s: str, items: int[]) -> int:
        ct_values.push(CTValue(type=t, i=i, s=s, items=items))
        ct_values.len() - 1
    message = verdict(T_TEXT, 0, "inner", [])
    next_value = verdict(T_OPT, 1, "", [message])
    print(cc_call(plain(T_NOT_UNION), 1, good))
    next_value = verdict(T_TEXT, 0, "text fails", [])
    print(cc_call(plain(T_NOT_UNION), 1, good))
    next_value = verdict(T_OPT, 0, "", [])
    loop t in [T_NOT_UNION, T_ALL_FAIL]: print(cc_call(plain(t), 1, good))
    loop t in [T_UNION, 23]:
        n = plain(t)
        before = nodes.len()
        print(cc_call(n, 1, good))
        print("{nodes[n].kind == .narrow} {nodes[n].kind == .conv} {nodes[n].aux} {nodes[n].a} {nodes[n].type} {nodes[n].flags} {before == nodes[n].a}")
        print(nodes[int(nodes[n].a)].type)
    cc_reset()
    show()
    print("constant ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_constant_checks_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare_narrow(compiler, tmp_path, release,
                            ('source_types', 'node_store', 'checker_types', 'checker_state', 'checker_tokens', 'evaluator_state', 'constant_checks'), DRIVER,
                            doubles={'services.jo': SERVICES, 'check_constant.jo': (ROOT / 'compiler/check_constant.jo').read_text()},
                            services=('checker_expr', 'ast', 'check', 'expr', 'types', 'util', 'errors', 'comptime', 'warn_if_ops', 'constant_folds'))
    assert output.endswith(b'constant ok\n')
    for text in (b'the validator of a constant check', b'bad pattern: inner', b'bad pattern: text fails', b'union [50, 51]', b'names a validator'):
        assert text in output, text
