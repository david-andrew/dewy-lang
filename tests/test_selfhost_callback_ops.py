"""Known-callback versions: bindings, budgets, requests and borrows match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'ir_types.dewy'
const NF_GENERIC = 1
const NF_GLOBAL = 2
const FK_LAMBDA = 1
const LF_ASSIGNED = 1
const LF_ADDR = 2
const LF_EXPOSED = 4
const LF_CAPTURED = 8
const LF_SHARED = 16
const LF_ALIAS = 32
const LF_BYREF = 64
const LF_MUTPARAM = 128
const LK_INST = 0
enum CV: none_, int_, refinement
enum HK: copy, drop
struct LFunc:
    kind: int
    inst: int
    hkind: HK
    htype: int
    name: str
struct SrcFile:
    is_dewy: bool
nodes: Node[] = [Node()]
lists: i32[]
lists2: i32[]
fns: FnInst[] = [FnInst()]
locals: Local[] = [Local()]
files: SrcFile[] = [SrcFile(false), SrcFile(true)]
lfuncs: LFunc[] = [LFunc(LK_INST, 0, .copy, 0, "base")]
ir: IrFn
stack_closure_params: {int: bool} = {}
unshareable: {int: bool} = {}
no_borrow: {int: bool} = {}
effectful: {int: bool} = {}
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
kid2 = (n: int, i: int) -> int: int(lists2[int(nodes[n].list2) + i])
nkids2 = (n: int) -> int: int(nodes[n].nlist2)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
pos_file = (pos: int) -> int: if pos >= 1000: 1 else: 0
closure_env_shareable = (f: int) -> bool: not unshareable.has(f)
closure_borrow_param = (f: int, i: int) -> bool: not no_borrow.has(f * 100 + i)
lf_of_inst = (f: int) -> int: 5000 + f
plain_read = (n: int) -> bool: not effectful.has(n)
'''

DRIVER = r'''
use 'callback_specialize.jo'
fresh = (k: NK) -> int:
    nodes.push(Node(kind=k, pos=1000))
    nodes.len() - 1
kids_of = (n: int, items: int[]):
    nodes[n].list = i32(lists.len()); nodes[n].nlist = i32(items.len())
    loop x in items: lists.push(i32(x))
kids2_of = (n: int, items: int[]):
    nodes[n].list2 = i32(lists2.len()); nodes[n].nlist2 = i32(items.len())
    loop x in items: lists2.push(i32(x))
chain = (depth: int) -> int:
    n = fresh(.block)
    loop i in [0..depth):
        p = fresh(.block)
        nodes[p].a = i32(n)
        n = p
    n
fn_of = (kind: int, decl: int, body: int, params: int[]) -> int:
    fns.push(FnInst(kind=i32(kind), decl=i32(decl), body=i32(body), params=params, sym="f{fns.len()}"))
    fns.len() - 1
lam = (f: int) -> int:
    n = fresh(.lambda)
    nodes[n].sym = i32(f)
    n
local_ident = (l: int) -> int:
    n = fresh(.ident)
    nodes[n].aux = 1; nodes[n].sym = i32(l)
    n
var_decl = (l: int, value: int) -> int:
    n = fresh(.vardecl)
    nodes[n].sym = i32(l); nodes[n].b = i32(value)
    n
call_of = (callee: int, args: int[]) -> int:
    n = fresh(.call)
    nodes[n].sym = i32(callee)
    kids_of(n, args)
    n
new_local = (flags: int) -> int:
    locals.push(Local(flags=i32(flags)))
    locals.len() - 1
seq = (items: int[]) -> int:
    n = fresh(.block)
    kids_of(n, items)
    n
sorted_dict = (d: {int: int}) -> str:
    keys = d.keys()
    keys.sort()
    s = ""
    loop k in keys: s = "{s} {k >> 32}/{k & 4294967295}={d[k]}"
    s
show = ():
    print("calls{sorted_dict(callback_calls)}")
    print("targets{sorted_dict(callback_targets)}")
    print("versions {callback_versions.len()}")
    keys = callback_counts.keys()
    keys.sort()
    loop k in keys: print("count {k} {callback_counts[k]}")
    loop i in [0..lfuncs.len()): print("lf {i} {lfuncs[i].kind} {lfuncs[i].inst} {int(lfuncs[i].hkind)} {lfuncs[i].htype} {lfuncs[i].name}")
main = ():
    print(callback_key(3, 7))
    print(callback_local(1))
    # The size budget: each child slot, the for/partial exclusions, nested lambdas, exhaustion.
    print("{callback_size(0, 5)} {callback_size(fresh(.block), 0)} {callback_size(lam(0), 9)} {callback_size(fresh(.block), 1)}")
    loop d in [0, 1, 10, 31, 32, 33, 40]: print("{d}: {callback_size(chain(d), 32)}")
    full = fresh(.block)
    nodes[full].a = i32(fresh(.block)); nodes[full].b = i32(fresh(.block)); nodes[full].c = i32(fresh(.block)); nodes[full].d = i32(fresh(.block))
    print(callback_size(full, 32))
    loop k in [NK.for_, NK.partial]:
        n = fresh(k)
        nodes[n].a = i32(fresh(.block)); nodes[n].b = i32(chain(2)); nodes[n].c = i32(chain(3)); nodes[n].d = i32(chain(4))
        print(callback_size(n, 32))
        nodes[n].c = i32(lam(0))
        print(callback_size(n, 32))
    listed = fresh(.block)
    kids_of(listed, [fresh(.block), chain(2)])
    kids2_of(listed, [chain(1), chain(3)])
    print(callback_size(listed, 32))
    # A callback's value: a lambda, generic or not, conversions, references, locals.
    tiny = fn_of(1, 0, chain(2), [])
    large = fn_of(1, 0, chain(40), [])
    shy = fn_of(1, 0, chain(1), [])
    unshareable[shy] = true
    known: {int: int} = {}
    bound = new_local(0)
    known[bound] = tiny
    conv = fresh(.conv); nodes[conv].a = i32(lam(tiny)); nodes[conv].aux = i32(int(CV.refinement))
    other = fresh(.conv); nodes[other].a = i32(lam(tiny)); nodes[other].aux = i32(int(CV.int_))
    ref = fresh(.fnref); nodes[ref].a = i32(lam(tiny)); nodes[ref].aux = 2
    plain_ref = fresh(.fnref); nodes[plain_ref].a = i32(lam(tiny)); nodes[plain_ref].aux = 1
    both = fresh(.conv); nodes[both].a = i32(ref); nodes[both].aux = i32(int(CV.refinement))
    generic = lam(tiny); nodes[generic].flags = 1
    other_kind = local_ident(bound); nodes[other_kind].aux = 2
    loop x in [lam(tiny), lam(large), lam(shy), conv, other, ref, plain_ref, both, generic, local_ident(bound), local_ident(new_local(0)), other_kind, fresh(.block)]:
        print(callback_value(x, known))
    # Bindings: flagged, assigned, generic, global, with kids; calls in preorder; lambdas opaque.
    target = fn_of(1, 0, chain(1), [])
    bad_flags = [1, 2, 4, 8, 16, 32, 64, 128]
    decls: int[]
    decl_locals: int[]
    loop f in bad_flags:
        l = new_local(f)
        decl_locals.push(l)
        decls.push(var_decl(l, lam(target)))
    ok = new_local(0)
    follow = new_local(0)
    ok_decl = var_decl(ok, lam(target))
    follow_decl = var_decl(follow, local_ident(ok))
    negative = var_decl(-1, lam(target))
    global_decl = var_decl(new_local(0), lam(target)); nodes[global_decl].flags = 2
    with_kids = var_decl(new_local(0), lam(target)); kids_of(with_kids, [fresh(.block)])
    not_callback = var_decl(new_local(0), fresh(.block))
    c1 = call_of(1, []); c2 = call_of(2, []); c3 = call_of(3, [])
    aux_call = call_of(1, []); nodes[aux_call].aux = 3
    inner = lam(0); nodes[inner].a = i32(call_of(4, []))
    for_n = fresh(.for_); nodes[for_n].a = i32(c2); nodes[for_n].c = i32(call_of(5, []))
    part = fresh(.partial); nodes[part].c = i32(c3); nodes[part].d = i32(call_of(6, []))
    two = fresh(.block); nodes[two].d = i32(call_of(7, []))
    list2 = fresh(.block); kids2_of(list2, [call_of(8, [])])
    body = seq([ok_decl, follow_decl, negative, global_decl, with_kids, not_callback, c1, aux_call, inner, for_n, part, two, list2] + decls)
    bound_table: {int: int} = {}
    calls: int[]
    callback_bindings(body, mut bound_table, mut calls)
    ks = bound_table.keys(); ks.sort()
    print("{ks} {bound_table.len()} {calls.len()}")
    loop c in calls: print("call {nodes[c].sym}")
    # Versions: refused kinds, budgets, caching, nesting, and per-function and global limits.
    small = chain(2)
    refuse = [FnInst(cabi=true, body=i32(small)), FnInst(has_env=true, body=i32(small)), FnInst(noinline=true, body=i32(small)), FnInst(export_name="x", body=i32(small)), FnInst()]
    loop r in refuse:
        fns.push(r)
        print(callback_request(fns.len() - 1, [target], 0))
    print(callback_request(fn_of(0, 0, chain(190), []), [target], 0))
    print(callback_request(fn_of(0, 0, small, []), [target], 4))
    # A version: its parameter binding, its own body's binding, and a nested request.
    leaf_param = new_local(0)
    leaf = fn_of(0, 0, seq([chain(1)]), [leaf_param])
    p1 = new_local(0); p2 = new_local(0)
    held = new_local(0)
    host = fn_of(0, 0, 0, [p1, p2])
    fns[host].body = i32(seq([var_decl(held, local_ident(p1)), call_of(leaf, [local_ident(held)])]))
    lf1 = callback_request(host, [target, -1], 0)
    print(lf1)
    print(callback_request(host, [target, -1], 0))
    lf2 = callback_request(host, [-1, target], 1)
    print(lf2)
    show()
    # Per-function limit of 8, then the global limit of 128.
    loop i in [0..12):
        print(callback_request(leaf, [100 + i], 0))
    show()
    loop i in [0..130):
        print(callback_request(fn_of(0, 0, chain(1), [new_local(0)]), [target], 0))
    show()
    # Scanning a call: mismatched arity, no callback, refused parameter, then published.
    callback_calls.clear(); callback_targets.clear(); callback_versions.clear(); callback_counts.clear()
    callee_param = new_local(0)
    callee = fn_of(0, 0, chain(1), [callee_param, new_local(0)])
    no_borrow[callee * 100 + 1] = true
    scan_known: {int: int} = {}
    loop c in [call_of(0, []), call_of(callee, []), call_of(callee, [fresh(.block), fresh(.block)]), call_of(callee, [fresh(.block), lam(target)])]:
        callback_scan(c, 3, scan_known, 0)
        show()
    hit = call_of(callee, [lam(target), fresh(.block)])
    callback_scan(hit, 3, scan_known, 0)
    callback_scan(hit, -9, scan_known, 0)
    deep_call = call_of(callee, [lam(target), fresh(.block)])
    callback_scan(deep_call, 3, scan_known, 9)
    show()
    # Preparing a whole program: none in a Dewy file, then one with a lambda and known callers.
    lfuncs = [LFunc(LK_INST, 0, .copy, 0, "base")]
    fns = [FnInst()]
    stack_closure_params[1] = true
    jo_decl = fresh(.fn_); nodes[jo_decl].pos = 1
    fn_of(1, jo_decl, chain(1), [])
    callback_prepare()
    print(stack_closure_params.len())
    show()
    dewy_decl = fresh(.fn_)
    t2 = fn_of(1, dewy_decl, chain(1), [])
    fn_of(1, 0, chain(1), [])
    prm = new_local(0)
    cal = fn_of(0, dewy_decl, chain(1), [prm])
    h = new_local(0)
    fn_of(0, dewy_decl, seq([var_decl(h, lam(t2)), call_of(cal, [local_ident(h)])]), [])
    fn_of(0, jo_decl, seq([var_decl(new_local(0), lam(t2))]), [])
    fn_of(0, 0, seq([var_decl(new_local(0), lam(t2))]), [])
    fn_of(0, dewy_decl, seq([chain(3)]), [])
    stack_closure_params[2] = true
    callback_prepare()
    print(stack_closure_params.len())
    show()
    # The hot lookup, and borrowing an argument.
    ir.fn_index = 5000 + fns.len() - 4
    print("{callback_local(h)} {callback_local(prm)}")
    ident_h = local_ident(h)
    ref_h = fresh(.fnref); nodes[ref_h].a = i32(ident_h); nodes[ref_h].aux = 2
    other_ref = fresh(.fnref); nodes[other_ref].a = i32(ident_h); nodes[other_ref].aux = 1
    wrong_aux = local_ident(h); nodes[wrong_aux].aux = 2
    fine = fresh(.block)
    bad = fresh(.block); effectful[bad] = true
    bad_ref = fresh(.fnref); nodes[bad_ref].a = i32(bad); nodes[bad_ref].aux = 2
    fine_ref = fresh(.fnref); nodes[fine_ref].a = i32(fine); nodes[fine_ref].aux = 2
    print(callback_arg_borrow(ident_h, [ident_h], 0, cal, 0))
    print(callback_arg_borrow(ref_h, [ref_h, fine, fine_ref], 0, cal, 0))
    print(callback_arg_borrow(other_ref, [other_ref], 0, cal, 0))
    print(callback_arg_borrow(wrong_aux, [wrong_aux], 0, cal, 0))
    print(callback_arg_borrow(fresh(.block), [fine], 0, cal, 0))
    print(callback_arg_borrow(local_ident(prm), [fine], 0, cal, 0))
    print(callback_arg_borrow(ident_h, [ident_h, fine, bad], 0, cal, 0))
    print(callback_arg_borrow(ident_h, [ident_h, bad_ref], 0, cal, 0))
    print(callback_arg_borrow(ident_h, [bad, ident_h], 1, cal, 0))
    no_borrow[cal * 100] = true
    print(callback_arg_borrow(ident_h, [ident_h], 0, cal, 0))
    no_borrow.clear()
    unshareable[t2] = true
    print(callback_arg_borrow(ident_h, [ident_h], 0, cal, 0))
    print("callback ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_callback_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/callback_specialize.jo').read_text()
    state = state[state.index('callback_calls: {'):]
    output = compare_narrow(compiler, tmp_path, release,
                            ('node_store', 'checker_state', 'ir_types', 'callback_ops'), DRIVER,
                            doubles={'services.jo': SERVICES, 'callback_specialize.jo': state},
                            services=('ast', 'check', 'expr', 'ir', 'lower', 'lower_closure_borrow', 'lower_closures', 'lower_primitives', 'lower_views', 'util'))
    assert output.endswith(b'callback ok\n')
    for text in (b'f12_callback', b'count ', b'calls 5'):
        assert text in output, text
