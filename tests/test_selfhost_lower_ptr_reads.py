"""Demanded pointer-read analysis matches frozen Jo, including fail-closed paths."""
import pytest
from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf, jo_doubles
from tests.test_selfhost_checker_resolve import DRIVER as BASE

JO = jo_doubles({
    'ast.jo': {
        'nkids': 'nkids = (n: int) -> int: int(nodes[n].nlist)',
        'nkids2': 'nkids2 = (n: int) -> int: int(nodes[n].nlist2)',
        'kid': 'kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])',
        'kid2': 'kid2 = (n: int, i: int) -> int: int(lists[int(nodes[n].list2) + i])',
        'has_flag': 'has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0',
        'flags': 'const NF_MUT = 1\nconst NF_EXTERN = 4\nconst NF_GLOBAL = 2048\nconst NF_AT = 2147483648',
    },
    'expr.jo': {'ntype': 'ntype = (n: int) -> int: int(nodes[n].type)', 'IN': 'enum IN:\n    none_, len, push, pop, insert, remove, clear, reserve, slice, syscall, memcpy, memset, sizeof,\n    arrdata, panic, assert, print, embed, from_bytes, to_bytes, argv, setlen, truncate, resize,\n    hash, alignof, unreachable, arrcap, fmt_struct, sqrt, vec_ctor, cfn_cast, wasm_call, callc, floor_,\n    ceil_, fabs, fmin, fmax, setjmp, longjmp, jump, shader, extend, clone_thread, atomic_add, atomic_cas, stack_ptr, fill, fmt_elem, gpu_kernel, cpu_features, code_sync, compute, compute_spirv, compute_textures,\n    read_fields, default_init, offset_unit, embed_dir, dewy_iter, dewy_iter_done, dewy_iter_value, json_fields, dewy_iter_pair, dewy_set,\n    static_assert, runtime_assert, dewy_print, dewy_fmt, dewy_fmt_elem, lend, loan_address, loan_load, loan_store, loan_length,\n    zeroed, relocate, take_slot, live_len, task_report, task_data, task_duration, arena_result, arrdata_permute, mul_hi, secret_wrap, secret_value, range_max, fixed_abs, integer_mode\n\n'},
    'types.jo': {'tkind': 'tkind = (t: int) -> TK: types[t].kind'},
    'check.jo': {'flags': "const LF_VALUEITER = 33554432 # readonly element of a Dewy array snapshot\nconst LF_PARAM = 1\nconst LF_MUTPARAM = 2\nconst LF_CAPTURE = 4\nconst LF_ALIAS = 8\nconst LF_ASSIGNED = 16\nconst LF_BYREF = 32\nconst LF_ADDR = 64     # address is taken (must live in memory)\nconst LF_RESIZED = 128 # the variable itself is written (not just its elements or fields)\nconst LF_CAPTURED = 256 # a closure captures this variable\nconst LF_DECL = 512     # declared by `x = value` / `x: T`\nconst LF_UNNARROWED = 2048  # a narrowed name (alias) whose variable was assigned another type\nconst LF_SOAELEM = 4096     # loop p in ps (ps a soa array): p stands for ps[i] (see soa_loop)\nconst LF_SOAMUT = 8192      # ... and the loop is `loop mut`\nconst LF_ELEMALIAS = 16384  # `mut x in xs` in a combined loop: x stands for xs[k] (writes to x write xs)\nconst LF_READ = 32768       # its value is read somewhere (not only the base of a write: v.f = 1)\nconst LF_QUIET = 65536      # a loop counter or part of `a, b = f()`: not warned about when unused\nconst LF_EXPOSED = 1048576 # raw storage exposure needs owned storage, including private captures\nconst LF_PARTBORROW = 16777216 # mutable array capture, admitted only by checked scoped partitions\nconst LF_OWNERBORROW = 8388608 # nonescaping resource capture: pointer, not an owned cell\nconst LF_VALUECAP = 262144  # Dewy capture owns a snapshot; outer links stop here\nconst LF_CONST = 131072     # Dewy const: one initialized value, no writes through the binding\nconst LF_VALUEPARAM = 524288 # a Dewy value parameter's own binding (dw_finish_function): a parameter\nconst LF_SHARED = 1024  # modified after a closure captured it, or by the closure: closures and"},
    'lower.jo': {
        'raw_view': 'raw_view = (n: int) -> bool: nodes[n].ival == 99',
        'checked_call_mutmask': 'checked_call_mutmask = (n: int) -> int:\n    if fail_mask: print("mask-error"); exit(41)\n    int(nodes[n].ival)',
    },
})

JO['ast.jo'] = "use 'node_store.dewy'\n" + JO['ast.jo']
JO['check.jo'] = "use 'checker_state.dewy'\n" + JO['check.jo']
JO['types.jo'] = "use 'checker_types.dewy'\n" + JO['types.jo']
JO['expr.jo'] = "use 'ast.jo'\n" + JO['expr.jo']
JO['lower.jo'] = "use 'ast.jo'\n" + JO['lower.jo']
# The moved analysis services still use this driver's controlled stand-ins.
JO['lower_analysis.dewy'] = r'''from p"lower.jo" import (raw_view as stub_raw_view checked_call_mutmask as stub_mask)
raw_view=(n:int64):>bool=>stub_raw_view(n)
checked_call_mutmask=(n:int64):>int64=>stub_mask(n)
'''
JO['lower_analysis.jo'] = "use 'lower.jo'\n"

DRIVER = BASE.split('main = ():')[0] + r'''
locals: Local[] = [Local()]
fns: FnInst[] = [FnInst()]
cur_fn = 0
fail_mask = false
lp_local = (flags: int = 0, alias: int = 0) -> int:
    l = locals.len(); locals.push(Local(flags=i32(flags), alias=i32(alias))); l
lp_node = (kind: NK, a: int = 0, b: int = 0, xs: int[] = [], t: int = 0) -> int:
    n = node(kind, a, 0, 0, xs); nodes[n].b = i32(b); nodes[n].type = i32(t); n
lp_ident = (l: int, t: int) -> int:
    n = lp_node(.ident, 0, 0, [], t); nodes[n].sym = i32(l); nodes[n].aux = i32(int(SK.local)); n
lp_data = (a: int) -> int:
    n = lp_node(.intrinsic, 0, 0, [a], T_RAWPTR); nodes[n].aux = i32(int(IN.arrdata)); n
lp_fn = (body: int, params: int[] = []) -> int:
    f = fns.len(); fns.push(FnInst(body=i32(body), decl=i32(lp_node(.fn_)), params=params)); f
lp_read = (p: int) -> int: lp_node(.index, p, 0, [], T_INT)
lp_call = (f: int, xs: int[]) -> int:
    n = lp_node(.call, 0, 0, xs); nodes[n].sym = i32(f); n
lp_reset = ():
    pr_parent.clear(); pr_written.clear(); pr_exposed.clear(); pr_done.clear(); pr_busy.clear(); pr_sites = []
'''

# Direct imports require the double module to own its exported storage.
for module, declarations in {
    'ast.jo': ['nodes: Node[] = [Node()]', 'lists: i32[]'],
    'check.jo': ['locals: Local[] = [Local()]', 'fns: FnInst[] = [FnInst()]'],
    'lower.jo': ['cur_fn = 0'],
}.items():
    JO[module] += '\n'.join(declarations) + '\n'
    for declaration in declarations:
        DRIVER = DRIVER.replace(declaration + '\n', '')
DRIVER = "use 'ast.jo'\nuse 'check.jo'\nuse 'lower.jo'\nuse 'expr.jo'\n" + DRIVER

MAIN = r'''main = ():
    prepare()
    a = lp_local(); av = lp_ident(a, int(tb_mk_array(T_INT))); p = lp_data(av)
    cur_fn = lp_fn(lp_read(p))
    assert(ptr_read_only(p) and not pr_exposed.has(a) and not pr_busy.has(cur_fn))
    assert(pr_sites.len() == 0 and not ptr_read_only(0))
    assert(pr_union(0, p) == p and pr_union(p, 0) == p)
    # Body replacement invalidates the function summary; a write marks the source.
    fns[cur_fn].body = i32(lp_node(.assign, lp_read(p), lp_node(.int_lit)))
    assert(not ptr_read_only(p) and pr_exposed.has(a))
    # Pointer propagation through a local and conditionals joins both classes.
    lp_reset()
    l = lp_local(); ident = lp_ident(l, T_RAWPTR)
    decl = lp_node(.vardecl, 0, p); nodes[decl].sym = i32(l)
    cur_fn = lp_fn(lp_node(.block, 0, 0, [decl, lp_read(ident)]))
    assert(ptr_read_only(p) and pr_find(-l) == pr_find(p))
    other = lp_data(av); choose = lp_node(.if_, lp_node(.bool_lit), p, [], T_RAWPTR); nodes[choose].c = i32(other)
    assert(pr_origin(choose) == pr_find(other) and pr_find(p) == pr_find(other))
    cast = lp_node(.cast, ident, 0, [], T_RAWPTR)
    offset = lp_node(.binary, cast, 0, [], T_RAWPTR); nodes[offset].aux = 4
    assert(pr_origin(offset) == pr_find(-l))
    # Calls only borrow pointer parameters after recursively proving their body.
    lp_reset()
    param = lp_local(); pi = lp_ident(param, T_RAWPTR)
    reader = lp_fn(lp_read(pi), [param])
    caller = lp_fn(lp_call(reader, [p])); cur_fn = caller
    assert(ptr_param_read(reader, 0, 1) and ptr_read_only(p))
    assert(not ptr_param_read(0, 0, 0) and not ptr_param_read(9999, 0, 1))
    assert(not ptr_param_read(reader, 1, 1) and not ptr_param_read(reader, 0, 2))
    fns[reader].cabi = true; assert(not ptr_param_read(reader, 0, 1)); fns[reader].cabi = false
    nodes[int(fns[reader].decl)].flags = i32(NF_EXTERN); assert(not ptr_param_read(reader, 0, 1)); nodes[int(fns[reader].decl)].flags = 0
    saved = fns[reader].decl; fns[reader].decl = 0; assert(not ptr_param_read(reader, 0, 1)); fns[reader].decl = saved
    saved = fns[reader].body; fns[reader].body = 0; assert(not ptr_param_read(reader, 0, 1)); fns[reader].body = saved
    # A recursive forwarding cycle fails closed, and restores the caller's sites.
    lp_reset()
    fns[reader].body = i32(lp_call(reader, [pi])); cur_fn = caller
    assert(not ptr_param_read(reader, 0, 1) and not ptr_read_only(p))
    assert(pr_busy.len() == 0 and pr_sites.len() == 0)
    # Captured/shared/by-reference locals cannot become readonly pointer classes.
    loop flag in [LF_CAPTURED, LF_CAPTURE, LF_SHARED, LF_ADDR, LF_BYREF, LF_ALIAS, LF_MUTPARAM]:
        x = lp_local(flag); root = pr_find(-x); assert(pr_written.has(root))
    # Exposure follows alias roots and nested places.
    aliased = lp_local(LF_ALIAS, av); ai = lp_ident(aliased, T_RAWPTR)
    field = lp_node(.field, lp_node(.unwrap, ai)); pr_expose(field)
    assert(pr_exposed.has(aliased) and pr_exposed.has(a))
    # Mut arguments, unknown calls, returns and named arguments all fail closed.
    loop mode in [0..4):
        lp_reset(); call = lp_call(reader, [p])
        if mode == 0: nodes[call].ival = 1
        if mode == 1: nodes[call].sym = 0
        if mode == 2: call = lp_node(.return_, p)
        if mode == 3: call = lp_call(reader, [lp_node(.namedarg, p, 0, [], T_RAWPTR)])
        cur_fn = lp_fn(call); assert(not ptr_read_only(p))
    # Lambda and function bodies are separate obligations, not child walks.
    lp_reset(); hidden = lp_node(.lambda, lp_node(.assign, lp_read(p), lp_node(.int_lit)))
    cur_fn = lp_fn(lp_node(.block, 0, 0, [lp_read(p), hidden]))
    assert(ptr_read_only(p))
    print("ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_lower_ptr_reads_twins(compiler, tmp_path, release):
    out = compare_leaf(compiler, tmp_path, release, DRIVER + MAIN,
                       extra_stems=('lower_ptr_reads',), jo_doubles=JO)
    assert out.endswith(b'ok\n')


def test_lower_ptr_reads_service_error(compiler, tmp_path):
    driver = DRIVER + 'main = ():\n    prepare(); fail_mask = true; pr_walk(lp_call(0, []))\n    print("unreachable")\n'
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('lower_ptr_reads',), jo_doubles=JO)
    assert out == b'mask-error\n'
