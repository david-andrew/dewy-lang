"""Deterministic callback walks and warning text match the frozen lowering checks."""
import pytest
from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf, jo_doubles
from tests.test_selfhost_lower_ptr_reads import DRIVER as BASE, JO as BASE_JO

JO = dict(BASE_JO)
JO.update(jo_doubles({'util.jo': {
    'name_of': 'name_of = (n: int) -> str: names[n]',
    'warn': '''warn = (p: int, msg: str):
    if fail_warn: print("warning-error"); exit(44)
    warnings.push("{p}:{msg}")
    if grow_warn:
        grow_warn = false; saved_nodes = nodes
        loop i in [0..128): nodes.push(Node())''',
}}))
JO['util.jo'] = "use 'ast.jo'\nuse 'node_store.dewy'\n" + JO['util.jo']
JO['ast.jo'] += '''kids = (n: int) -> int[]:
    xs: int[]
    loop i in [0..nkids(n)): xs.push(kid(n, i))
    xs
kids2 = (n: int) -> int[]:
    xs: int[]
    loop i in [0..nkids2(n)): xs.push(kid2(n, i))
    xs
'''
JO['check.jo'] += 'struct DTModule:\n    name: i32\nmodules: DTModule[] = [DTModule()]\n'
JO['lower.jo'] += 'in_lib = (p: int) -> bool: p >= 100000\nplace_var = (n: int) -> int:\n    if nodes[n].kind == .ident: return n\n    0\n'
JO['lower_analysis.dewy'] += r'''from p"lower.jo" import (place_var as stub_place_var)
place_var=(n:int64):>int64=>stub_place_var(n)
'''
JO['lower_races.dewy'] = 'from p"lower.jo" import (in_lib as stub_in_lib)\nin_lib=(p:int64):>bool=>stub_in_lib(p)\n'
JO['lower_races.jo'] = "use 'lower.jo'\n"
JO['types.jo'] += 'prune = (t: int) -> int: t\ntype_str = (t: int) -> str: if types[t].bits == 42: "Rng" else: "Other"\n'
DRIVER = BASE.split('lp_reset =')[0] + r'''
use 'util.jo'
warnings: str[]
fail_warn = false
grow_warn = false
saved_nodes: Node[]
dt_name = (text: str) -> int: names.push(text); names.len() - 1
dt_global = () -> int:
    n = lp_ident(0, T_INT); nodes[n].aux = i32(int(SK.global)); nodes[n].name = i32(dt_name("counter")); n
dt_fn = (name: str, body: int, library: bool = false) -> int:
    f = lp_fn(body); d = int(fns[f].decl); nodes[d].name = i32(dt_name(name))
    if library: nodes[d].pos = 100000
    f
dt_ref = (f: int) -> int:
    n = lp_node(.fnref, 0, 0, [], int(tb_mk_fn([], T_VOID, 0))); nodes[n].sym = i32(f); n
'''
MAIN = r'''main = ():
    prepare(); modules[0].name = i32(dt_name("netplay"))
    global = dt_global(); write = lp_node(.assign, global, lp_node(.int_lit))
    clock = dt_fn("time", 0, true); call = lp_call(clock, [])
    body = lp_node(.block, 0, 0, [write, call]); target = dt_fn("tick", body)
    api = dt_fn("session", 0); fns[api].deterministic = true
    ref = dt_ref(target)
    grow_warn = true; det_check(api, [ref], 1)
    assert(not grow_warn and warnings.len() == 2 and det_done.has(target))
    # Named summaries stop repeated work, including recursive call cycles.
    det_check(api, [ref], 1); assert(warnings.len() == 2)
    cycle = lp_call(target, []); node_set_list(mut nodes, mut lists, body, [cycle, write, call])
    det_done.clear(); warnings.clear(); det_check(api, [ref], 1); assert(warnings.len() == 2)
    print(warnings)
    # Check mode finds deterministic entry calls in checked user bodies.
    warnings.clear(); det_done.clear(); entry = dt_fn("entry", lp_call(api, [ref])); fns[entry].state = 2
    det_check_program(); assert(warnings.len() == 2)
    # Library call sites and non-function arguments do not start a walk.
    warnings.clear(); det_done.clear(); det_check(api, [ref], 100000); det_check(api, [global], 1)
    assert(warnings.len() == 0)
    # Explicit RNG state and unix_time(Date) avoid ambient-read warnings.
    rng = types.len(); types.push(TypeInfo(kind=.struct_, bits=42))
    random = dt_fn("random", 0, true); fns[random].ptypes = [rng]
    det_scan(lp_call(random, []), "rng"); assert(warnings.len() == 0)
    types[rng].bits = 0; det_scan(lp_call(random, []), "rng"); assert(warnings.len() == 1)
    unix = dt_fn("unix_time", 0, true); fns[unix].ptypes = [T_INT]
    det_scan(lp_call(unix, []), "clock"); assert(warnings.len() == 1)
    fns[unix].ptypes = []; det_scan(lp_call(unix, []), "clock"); assert(warnings.len() == 2)
    # Warning categories and exact text survive for time, random, frame and input.
    loop nm in ["randn", "shuffle", "fps", "key_down", "elapsed", "now"]:
        det_scan(lp_call(dt_fn(nm, 0, true), []), "callback")
    print(warnings)
    # Mut arguments, collection updates and mut loops name global writes.
    warnings.clear(); c = lp_call(0, [global]); nodes[c].ival = 1; det_scan(c, "mut")
    update = lp_node(.intrinsic, 0, 0, [global]); nodes[update].aux = i32(int(IN.push)); det_scan(update, "push")
    loopn = lp_node(.for_, global); nodes[loopn].flags = i32(NF_MUT); det_scan(loopn, "loop")
    assert(warnings.len() == 3)
    det_target(lp_ident(lp_local(), T_INT), "local", 1); assert(warnings.len() == 3)
    # Lambda bodies are only traversed when the callback itself is supplied.
    node_set_list(mut nodes, mut lists, body, [write, call]); det_done.clear()
    warnings.clear(); lam = lp_node(.lambda, 0, 0, [], int(nodes[ref].type)); nodes[lam].sym = i32(target)
    det_scan(lam, "hidden"); assert(warnings.len() == 0)
    det_arg(lam, "tick"); assert(warnings.len() == 2)
    det_done.clear(); warnings.clear(); partial = lp_node(.partial, ref); nodes[partial].aux = 1
    det_arg(lp_node(.conv, partial), "tick"); assert(warnings.len() == 2)
    det_done.clear(); warnings.clear(); nodes[partial].aux = 0; nodes[partial].sym = i32(target)
    det_arg(partial, "tick"); assert(warnings.len() == 2)
    print("ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_lower_determinism_twins(compiler, tmp_path, release):
    out = compare_leaf(compiler, tmp_path, release, DRIVER + MAIN,
                       extra_stems=('lower_determinism',), jo_doubles=JO)
    assert out.endswith(b'ok\n') and b'reads the clock' in out and b'takes random numbers' in out


def test_lower_determinism_service_error(compiler, tmp_path):
    driver = DRIVER + 'main = ():\n    prepare(); fail_warn = true; det_target(dt_global(), "tick", 1)\n    print("unreachable")\n'
    out = compare_leaf(compiler, tmp_path, False, driver, status=44,
                       extra_stems=('lower_determinism',), jo_doubles=JO)
    assert out == b'warning-error\n'
