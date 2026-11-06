"""Generic local closures: scopes, instances, defaults, layouts and matching match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
const FK_LAMBDA = 1
const LF_PARAM = 1
const LF_UNNARROWED = 2
const LF_FROM_CAPTURE = 4
const NF_CHECKED = 8
const NF_MUT = 16
const T_VOID = 1
const T_FN = 2
const T_NUM = 3
nodes: Node[] = [Node()]
lists: i32[]
ctxs: FnCtx[]
cx = -1
check_scopes = CheckerScope()
syms: Sym[] = [Sym()]
locals: Local[] = [Local()]
fns: FnInst[] = [FnInst()]
decl_infos: DeclInfo[] = [DeclInfo()]
decl_info_of: {int: int} = {}
fn_instances: {FnInstanceKey: int} = {}
loop_serials: int[]
types: TypeInfo[] = [TypeInfo(), TypeInfo(kind=.void_), TypeInfo(kind=.fn_), TypeInfo(kind=.int_)]
narrowed: {int: int} = {}
pl_on = false
pl_inst_decls: int[]
dewy_literal_method_name = 0
method_decls: {int: bool} = {}
void_bodies: {int: bool} = {}
body_marks_void: {int: bool} = {}
body_grows = 0
next_fn_type = 5000
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
clone = (n: int) -> int:
    if n == 0: return 0
    copy = nodes[n]
    nodes.push(copy)
    r = nodes.len() - 1
    print("clone {n} = {r}")
    if int(nodes[n].nlist) > 0:
        items: int[]
        loop i in [0..nkids(n)): items.push(clone(kid(n, i)))
        set_list(r, items)
    if nodes[n].kind == .fn_ and nodes[n].b != 0:
        b = clone(int(nodes[n].b))
        nodes[r].b = i32(b)
    # (an arena that moves under a caller's cached element)
    loop i in [0..64): nodes.push(Node(kind=.block))
    r
cur_mod = () -> int: 11
new_sym = (name: int, kind: SK, r: int, decl: int) -> int:
    syms.push(Sym(name=i32(name), kind=kind, ref=i32(r), decl=i32(decl)))
    print("new_sym {name} {int(kind)} {r} {decl} = {syms.len() - 1}")
    syms.len() - 1
push_scope_sym = (name: int, sym: int):
    loop check_scopes.top.len() <= name: check_scopes.top.push(-1)
    check_scopes.names.push(name)
    check_scopes.syms.push(sym)
    check_scopes.prev.push(check_scopes.top[name])
    check_scopes.top[name] = check_scopes.names.len() - 1
scope_mark = () -> int: check_scopes.names.len()
scope_reset = (mark: int):
    loop check_scopes.names.len() > mark:
        name = check_scopes.names.pop()
        check_scopes.syms.pop()
        check_scopes.top[name] = check_scopes.prev.pop()
new_inst = (kind: int, m: int, base: str) -> int:
    fns.push(FnInst(kind=i32(kind), mod=i32(m), sym=base))
    print("new_inst {kind} {m} {base} = {fns.len() - 1}")
    fns.len() - 1
new_local = (name: int, t: int, pos: int) -> int:
    locals.push(Local(name=i32(name), type=i32(t), pos=pos))
    print("new_local {name} {t} {pos} = {locals.len() - 1}")
    locals.len() - 1
narrowed_var = (l: int) -> int: narrowed.get(l) ?? 0
subst = (t: int, targs: int[]) -> int:
    print("subst {t} {targs}")
    if targs.len() > 0: t + targs[0] else: t
push_type_params = (decl: int, targs: int[]): print("push_type_params {decl} {targs}")
decl_info = (decl: int) -> int:
    if not decl_info_of.has(decl):
        decl_infos.push(DeclInfo())
        decl_info_of[decl] = decl_infos.len() - 1
    decl_info_of[decl]
syntactic_void = (body: int) -> bool:
    print("syntactic_void {body}")
    void_bodies.has(body)
copy_write_warnings = (f: int): print("copy_write_warnings {f}")
check_lambda_body = (f: int, lam: int, hint: int):
    print("body {f} {lam} {hint} cx={cx} frames={ctxs.len()} top={check_scopes.names.len()} serials={loop_serials} parent={if cx >= 0: int(ctxs[cx].parent) else: -2} floor={if cx >= 0: int(ctxs[cx].floor) else: -2}")
    # (a body can make more functions, moving the arena)
    loop i in [0..body_grows): fns.push(FnInst())
    if body_marks_void.has(int(fns[f].decl)):
        fns[f].aux_void = true
        fns[f].ret = i32(T_NUM)
zonk_tree = (root: int): print("zonk_tree {root}")
zonk = (t: int) -> int:
    if t >= 9000: return t - 9000
    t
has_var = (t: int) -> bool: t == 999
mk_type = (t: TypeInfo, args: int[]) -> int:
    print("mk_type {int(t.kind)} {t.st} {args}")
    types.push(t)
    types.len() - 1
tkind = (t: int) -> TK: types[t].kind
targ = (t: int, i: int) -> int: 700 + i
mk_fn = (params: int[], ret: int, mutmask: int, labels: int = 0, defaults: int = 0, pack: bool = false) -> int:
    print("mk_fn {params} {ret} {mutmask} {labels} {defaults} {pack}")
    next_fn_type += 1
    next_fn_type
decl_fn_labels = (decl: int) -> int: decl + 1000
align_up = (x: int, a: int) -> int: (x + a - 1) & ~(a - 1)
tsize = (t: int) -> int: t * 3
talign = (t: int) -> int: if t > 5: 16 else: 4
is_shared = (l: int) -> bool: int(locals[l].flags) & 128 != 0
check_cell_type = (l: int): print("check_cell_type {l}")
store_type = (l: int) -> int: int(locals[l].type)
fn_sig = (decl: int) -> FnSig: decl_infos[decl_info(decl)].sig
check_expr = (n: int, e: int) -> int:
    print("check_expr {n} {e} cx={cx} inst={int(ctxs[cx].inst)} parent={int(ctxs[cx].parent)} floor={int(ctxs[cx].floor)} mod={int(ctxs[cx].mod)}")
    n
finalize_literal = (n: int) -> int:
    print("finalize_literal {n}")
    n
fn_value = (n: int, expected: int, explicit_types: int[] = [], mod: int = -1, closure: int = 0) -> int:
    print("fn_value {n} {expected} {explicit_types} {mod} {closure} same={nodes[closure].kind == nodes[n].kind}")
    77
match_type = (pat: int, a: int, binds: mut int[], depth: int) -> int:
    print("match {pat} {a} {depth}")
    if pat == 100: return -1
    if pat == 101: return 1
    if pat >= 200:
        binds[pat - 200] = a
        return 2
    0
mk_ident_local = (l: int, pos: int) -> int:
    n = mk(.ident, pos)
    nodes[n].sym = i32(l)
    loop i in [0..64): nodes.push(Node(kind=.block))
    n
opt_rest_rebase = (al: int, l: int, pos: int) -> int:
    print("opt_rest_rebase {al} {l} {pos}")
    mk(.if_, pos)
mk_callable_contract = (base: int, contract: int, capability: int = 0) -> int:
    print("mk_callable_contract {base} {contract} {capability}")
    base + 1
dewy_is_method = (decl: int) -> bool: method_decls.has(decl)
fatal = (pos: int, msg: str): print("fatal {pos}: {msg}")
name_of = (n: int) -> str: "name{n}"
intern = (s: str) -> int:
    print("intern {s}")
    42
'''

DRIVER = r'''
use 'poly_closure.jo'
frame_text = (c: FnCtx) -> str: "<{c.inst} {c.parent} {c.ret} {c.infer_ret} {c.loop_depth} {c.mod} {c.floor}>"
family_text = (i: int) -> str:
    s = "family {i}: {poly_families[i].decl} {poly_families[i].envfn}"
    scope = poly_families[i].scope
    loop c in scope.frames: s = "{s} {frame_text(c)}"
    "{s} names {scope.names} symbols {scope.symbols} loops {scope.loops}"
fn_text = (f: int) -> str:
    x = fns[f]
    "fn {f}: decl={x.decl} body={x.body} targs={x.targs} ptypes={x.ptypes} ret={x.ret} sym={x.sym} state={x.state} kind={x.kind} env={x.has_env} size={x.env_size} mod={x.mod} target={x.target} fntype={x.fntype} made_in={x.made_in} gdepth={x.gdepth} use_pos={x.use_pos} void={x.aux_void} caps={x.caps.len()}"
decl_with_sig = (body: int, params: int[], sig: FnSig) -> int:
    d = mk(.fn_, 900)
    nodes[d].b = i32(body)
    nodes[d].aux = 1
    nodes[d].mod = 3
    set_list(d, params)
    decl_infos[decl_info(d)].sig = sig
    d
param = (name: int, default_value: int, flags: int) -> int:
    p = mk(.param, 800 + name)
    nodes[p].name = i32(name); nodes[p].b = i32(default_value); nodes[p].a = i32(name + 500); nodes[p].flags = i32(flags)
    p
ctx = (inst: int, parent: int, floor: int):
    ctxs.push(FnCtx(inst=i32(inst), parent=i32(parent), floor=i32(floor), mod=i32(inst + 20), ret=i32(inst + 30), loop_depth=i32(inst + 40)))
    cx = ctxs.len() - 1
main = ():
    # A scope: the enclosing chain, a hidden name, a shadowed name, a narrowing frozen once.
    ctx(1, -1, 0)
    ctx(2, 0, 0)
    ctx(3, 1, 2)
    hidden = new_sym(61, .local, 0, 1)
    push_scope_sym(61, hidden)
    below = new_sym(62, .local, 0, 1)
    push_scope_sym(62, below)
    shadowed = new_sym(63, .global, 5, 2)
    push_scope_sym(63, shadowed)
    shadowing = new_sym(63, .global, 6, 3)
    push_scope_sym(63, shadowing)
    base_local = new_local(70, 3, 7)
    alias_of = mk(.narrow, 8)
    nodes[alias_of].a = 3
    narrowed_local = new_local(71, 3, 9)
    locals[narrowed_local].alias = i32(alias_of)
    narrowed[narrowed_local] = base_local
    twice = new_local(72, 3, 9)
    locals[twice].alias = i32(alias_of)
    narrowed[twice] = narrowed_local
    plain_sym = new_sym(64, .local, base_local, 4)
    push_scope_sym(64, plain_sym)
    narrow_sym = new_sym(65, .local, narrowed_local, 4)
    push_scope_sym(65, narrow_sym)
    twice_sym = new_sym(66, .local, twice, 4)
    push_scope_sym(66, twice_sym)
    loop_serials = [5, 6]
    scope = poly_scope()
    poly_families.push(PolyFamily(50, 51, scope))
    print(family_text(1))
    print("locals {locals.len()}")
    # Freezing: a known alias, no outer, unnarrowed flag, an optional's rest, and a chain.
    frozen: {int: int} = {}
    print(poly_freeze_narrowing(base_local, mut frozen))
    u = new_local(73, 3, 9)
    locals[u].flags = i32(LF_UNNARROWED); locals[u].alias = i32(alias_of)
    narrowed[u] = base_local
    print(poly_freeze_narrowing(u, mut frozen))
    rest_alias = mk(.if_, 8)
    r = new_local(74, 3, 11)
    locals[r].alias = i32(rest_alias)
    narrowed[r] = base_local
    first = poly_freeze_narrowing(r, mut frozen)
    print("{first} {poly_freeze_narrowing(r, mut frozen)} {locals[first].alias} {locals[first].pos} {nodes[int(locals[first].alias)].kind == .if_}")
    a2 = new_local(75, 3, 12)
    locals[a2].alias = i32(alias_of)
    narrowed[a2] = narrowed_local
    second = poly_freeze_narrowing(a2, mut frozen)
    al = int(locals[second].alias)
    print("{second} {al != alias_of} {nodes[al].kind == .narrow} {nodes[int(nodes[al].a)].sym} {nodes[int(nodes[al].a)].kind == .ident} {frozen.len()}")
    # Entering a family: its frames rebased over the caller's scope; leaving restores everything.
    before = check_scopes.names.len()
    saved = poly_enter(1)
    print("{saved.current} {saved.frames} {saved.mark} {saved.loops} cx={cx} serials={loop_serials} names={check_scopes.names.len() - before}")
    loop i in [saved.frames..ctxs.len()): print(frame_text(ctxs[i]))
    print(check_scopes.top[65] >= before)
    poly_leave(saved)
    print("{cx} {ctxs.len()} {loop_serials} {check_scopes.names.len()} {check_scopes.top[63]}")
    # Declaring a family: its own node, environment, pending warnings up the chain, with and without an expected function type.
    sig = FnSig(params=[900, 901], ret=0, mutmask=0, ntp=2)
    lam_body = mk(.block, 3)
    lam = mk(.lambda, 2)
    nodes[lam].b = i32(lam_body); nodes[lam].sym = 7; nodes[lam].name = 8; nodes[lam].mod = 9
    d0 = nodes.len()
    decl_infos[decl_info(d0)].sig = sig
    print(check_poly_lambda(lam, 0))
    print(family_text(2))
    print("{nodes[d0].sym} {nodes[d0].mod} {nodes[d0].name} {nodes[d0].aux} {nodes[d0].b} {nodes[lam].aux} {nodes[lam].type}")
    print(fn_text(int(poly_families[2].envfn)))
    pending = poly_pending_warnings.keys(); pending.sort()
    print(pending)
    lam2 = mk(.lambda, 2)
    decl_infos[decl_info(nodes.len())].sig = sig
    print(check_poly_lambda(lam2, T_FN))
    lam3 = mk(.lambda, 2)
    decl_infos[decl_info(nodes.len())].sig = sig
    print(check_poly_lambda(lam3, T_NUM))
    # Warnings: each active once; a second pass does nothing.
    poly_finish_warnings()
    poly_finish_warnings()
    pending = poly_pending_warnings.keys(); pending.sort()
    loop k in pending: print("{k} {poly_pending_warnings[k]}")
    # Instances: new, repeated, type argument unresolved, generic depth, signature with a return, contract.
    poly_families.push(PolyFamily(100, 101, scope))
    decl_infos[decl_info(100)].sig = sig
    rb = mk(.block, 4)
    d = decl_with_sig(rb, [], FnSig(params=[11, 12], ret=13, mutmask=1, ntp=1, contract=44))
    nodes[d].aux = i32(poly_families.len() - 1)
    f = poly_inst(d, [9003], 400)
    print(fn_text(f))
    print(poly_inst(d, [3], 401))
    print(decl_infos[decl_info(100)].insts)
    ctx(f, 2, 0)
    fns[f].targs = [3]
    fns[f].gdepth = 7
    pl_on = true
    body_grows = 40
    f2 = poly_inst(d, [999, 4], 402)
    print(fn_text(f2))
    print(pl_inst_decls)
    pl_on = false
    fns[f].gdepth = 500
    body_grows = 0
    print(fn_text(poly_inst(d, [5], 403)))
    fns[f].targs = []
    print(fn_text(poly_inst(d, [6], 404)))
    cx = -1
    print(fn_text(poly_inst(d, [7], 405)))
    # No return in the signature: a recursive call sees no return yet.
    nb = mk(.block, 4)
    no_ret = decl_with_sig(nb, [], FnSig(params=[11], ret=0, mutmask=2, ntp=1))
    nodes[no_ret].aux = i32(poly_families.len() - 1)
    g = poly_inst(no_ret, [1], 410)
    print(fn_text(g))
    fns[g].ret = 0
    fns[g].state = 1
    void_bodies[nb] = true
    print(poly_inst(no_ret, [1], 411))
    print(fn_text(g))
    fns[g].ret = 0
    fns[g].state = 0
    print(poly_inst(no_ret, [1], 412))
    fns[g].state = 1
    void_bodies.clear()
    print(poly_inst(no_ret, [1], 413))
    method_decls[no_ret] = true
    print(poly_inst(no_ret, [1], 414))
    dewy_literal_method_name = 88
    print(poly_inst(no_ret, [1], 415))
    # A void marked during checking that then returns a value.
    body_marks_void[no_ret] = true
    print(fn_text(poly_inst(no_ret, [2], 416)))
    method_decls.clear()
    print(fn_text(poly_inst(no_ret, [3], 417)))
    dewy_literal_method_name = 0
    body_marks_void.clear()
    # Reference.
    src = mk(.lambda, 21)
    ref = poly_fnref(src, f)
    print("{nodes[ref].kind == .fnref} {nodes[ref].pos} {nodes[ref].a == src} {nodes[ref].sym} {nodes[ref].aux} {nodes[ref].type} {nodes[ref].flags}")
    # Matching against a function type.
    match_family = (ptypes: int[], ret: int, mask: int, ntp: int) -> int:
        dm = mk(.fn_, 2)
        decl_infos[decl_info(dm)].sig = FnSig(params=ptypes, ret=i32(ret), mutmask=i32(mask), ntp=i32(ntp))
        poly_families.push(PolyFamily(dm, 0, scope))
        types.push(TypeInfo(kind=.polyfn, st=i32(poly_families.len() - 1)))
        types.len() - 1
    target = (nargs: int, mask: int, elem: int) -> int:
        types.push(TypeInfo(kind=.fn_, nargs=i32(nargs), mutmask=i32(mask), elem=i32(elem)))
        types.len() - 1
    loop item in [(match_family([200], 0, 0, 1), target(1, 0, 0)), (match_family([200, 200], 0, 0, 1), target(1, 0, 0)), (match_family([200], 0, 1, 1), target(1, 0, 0)), (match_family([100], 0, 0, 0), target(1, 0, 0)), (match_family([101], 0, 0, 0), target(1, 0, 0)),
                  (match_family([200], 0, 0, 2), target(1, 0, 0)), (match_family([200], 201, 0, 2), target(1, 0, 9)), (match_family([50], 100, 0, 0), target(1, 0, 9)), (match_family([50], 101, 0, 0), target(1, 0, 9)), (match_family([], 0, 0, 0), target(0, 0, 0))]:
        print(poly_matches(item.0, item.1))
    # An environment's layout: captures unioned by outer binding across instances, offsets shared.
    d_env = mk(.fn_, 2)
    env = new_inst(1, 0, "env")
    poly_families.push(PolyFamily(d_env, env, scope))
    fam = poly_families.len() - 1
    outer_a = 301; outer_b = 302
    i1 = new_local(1, 3, 1); i2 = new_local(2, 8, 1); j1 = new_local(1, 3, 1); j2 = new_local(2, 8, 1); k1 = new_local(3, 2, 1)
    locals[i1].flags = 1
    locals[j1].flags = 2
    locals[j2].flags = 128
    locals[k1].flags = 128
    inst1 = new_inst(1, 0, "a"); inst2 = new_inst(1, 0, "b")
    fns[inst1].caps = [Capture(outer=i32(outer_a), inner=i32(i1)), Capture(outer=i32(outer_b), inner=i32(i2))]
    fns[inst2].caps = [Capture(outer=i32(outer_b), inner=i32(j2)), Capture(outer=i32(outer_a), inner=i32(j1)), Capture(outer=303, inner=i32(k1))]
    decl_infos[decl_info(d_env)].insts = [inst1, inst2]
    poly_env_layout(fam)
    loop l in [i1, i2, j1, j2, k1]: print("{l} {locals[l].flags} {locals[l].env_off}")
    print("{fns[env].env_size} {fns[inst1].env_size} {fns[inst2].env_size} {fns[env].caps.len()}")
    fns[env].env_size = 99
    locals[i1].env_off = -5
    poly_env_layout(fam)
    print("{locals[i1].env_off} {fns[inst1].env_size}")
    # A default variant: no omission, cached, supplied and omitted, mutable and `_` parameters, missing binding, trailing body.
    print(poly_default_variant(d, [1, 2]))
    p1 = param(81, mk(.int_lit, 5), 0)
    p2 = param(82, mk(.int_lit, 6), 0)
    p3 = param(83, mk(.int_lit, 7), NF_MUT)
    p4 = param(84, mk(.int_lit, 8), NF_MUT)
    under = param(85, mk(.int_lit, 9), 0)
    vd = (name: int) -> int:
        n = mk(.vardecl, 30)
        nodes[n].name = i32(name)
        n
    tail = mk(.call, 31)
    body = mk(.block, 32)
    set_list(body, [vd(81), vd(82), vd(85), tail])
    dv = decl_with_sig(body, [p1, p2, p3, p4, under], FnSig(params=[1, 2, 3, 4, 5], ret=9, mutmask=0, ntp=0))
    loop args in [[1, 0, 1, 0, 1], [0, 1, 0, 1, 0], [1, 1, 1, 1, 0], [0, 0, 0, 0, 0]]:
        v = poly_default_variant(dv, args)
        print("variant {v == dv} {poly_default_variant(dv, args) == v} {nodes[v].mod}")
        vs = fn_sig(v)
        print("sig {vs.params} {vs.mutmask} {vs.ret} kids {nkids(v)}")
        vb = int(nodes[v].b)
        loop i in [0..nkids(vb)):
            b = kid(vb, i)
            print("  {nodes[b].kind == .vardecl} {nodes[b].name} {nodes[b].a} {nodes[nodes[b].b].ival} {nodes[b].aux2}")
    # Under-score parameter's binding made anew, when no synthetic one exists for it.
    fn_mark = fn_sig(dv)
    print(fn_mark.params)
    # Default type: the closure's frame, an owner under it, earlier parameters as locals.
    poly_families.push(PolyFamily(dv, 0, scope))
    nodes[dv].aux = i32(poly_families.len() - 1)
    print("{poly_default_type(dv, 2, [5]) != 0} {cx} {ctxs.len()}")
    ctx(g, -1, 0)
    fns[g].gdepth = 3
    print("{poly_default_type(dv, 0, []) != 0} {cx} {ctxs.len()}")
    print(fn_text(fns.len() - 1))
    ctx(0, -1, 0)
    print("{poly_default_type(dv, 1, [1, 2]) != 0} {cx} {ctxs.len()}")
    print(fn_text(fns.len() - 1))
    print("poly ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_poly_ops_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/poly_closure.jo').read_text()
    state = state[state.index('struct PolyScope'):]
    output = compare_narrow(compiler, tmp_path, release,
                            ('node_store', 'checker_types', 'checker_state', 'poly_ops'), DRIVER,
                            doubles={'services.jo': SERVICES, 'poly_closure.jo': "use 'checker_state.dewy'\n" + state},
                            services=('ast', 'check', 'checker_expr', 'checker_signature', 'dewy_methods', 'effect_contracts', 'expr', 'lower_storage', 'types', 'util'))
    assert output.endswith(b'poly ok\n')
    for text in (b'cannot infer a generic', b'recursive method', b'mk_callable_contract', b'a recursive generic closure that returns', b'more than 500', b'opt_rest_rebase'):
        assert text in output, text
