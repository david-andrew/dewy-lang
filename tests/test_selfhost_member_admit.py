"""members(U) replay: admission, shared types, copies and domains match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_tokens.dewy'
use 'checker_types.dewy'
use 'refinement_types.dewy'
const NF_RDONLY = 1
const NF_AT = 2
const LF_ALIAS = 1
const LF_CAPTURE = 2
const LF_CAPTURED = 4
const LF_BYREF = 8
const LF_ADDR = 16
const LF_CONST = 32
const T_STR = 1
const T_INT = 2
const T_MATH_INT = 3
const T_VAR = 4
const T_BOOL = 5
const T_FLOAT = 6
const T_SET = 7
const T_INTS = 8
const T_MAP = 9
const T_BAD_MAP = 10
const T_OTHER = 11
const T_LOOP = 12
const T_VOID = 13
enum CV: none_, refinement, set_text, int_
enum IN: none_, len, push, to_bytes, runtime_assert, static_assert, panic
nodes: Node[] = [Node()]
lists: i32[]
lists2: i32[]
locals: Local[] = [Local()]
globals: Global[] = [Global()]
syms: Sym[] = [Sym()]
fns: FnInst[] = [FnInst()]
ctxs: FnCtx[] = [FnCtx()]
cx = 0
check_scopes = CheckerScope()
const_views: int[]
copy_writes: {int: int} = {}
exact_stores: {int: int} = {}
ref_narrowing: {int: int} = {}
fact_divisors: {int: int} = {}
fact_requests: FactRequest[]
refine_requests: FactRequest[]
str_sets: str[][] = [[], ["a", "b"], ["a", "b", "c"], ["c", "x"], ["x", "y"]]
sibling_known: {int: int} = {}
sibling_flow: {int: int} = {}
wi_fact_calls: {int: int} = {}
ide_on = false
debug_vars = false
shown_warnings: str[]
types: TypeInfo[] = [TypeInfo(), TypeInfo(kind=.str_), TypeInfo(kind=.int_), TypeInfo(kind=.int_), TypeInfo(kind=.var), TypeInfo(kind=.bool_), TypeInfo(kind=.float_), TypeInfo(kind=.enum_), TypeInfo(kind=.array, elem=2),
                     TypeInfo(kind=.struct_, st=0), TypeInfo(kind=.struct_, st=1), TypeInfo(kind=.fn_), TypeInfo(kind=.array, elem=12), TypeInfo(kind=.void_)]
structs: StructInfo[] = [StructInfo(ntargs=2), StructInfo(ntargs=1)]
prelude_decls: {int: bool} = {}
in_set: {int: int} = {}
block_hook: () -> void = ():
    pass
names: {str: int} = {}
name_texts: str[] = [""]
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
nkids2 = (n: int) -> int: int(nodes[n].nlist2)
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
kid_c = (n: int) -> int: int(nodes[n].c)
kid_d = (n: int) -> int: int(nodes[n].d)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
intern = (s: str) -> int:
    if let id = names.get(s): return id
    name_texts.push(s)
    names[s] = name_texts.len() - 1
    names[s]
name_of = (n: int) -> str: name_texts[n]
pos_str = (pos: int) -> str: "p{pos}"
clone = (n: int) -> int:
    print("clone {n}")
    copy = nodes[n]
    nodes.push(copy)
    nodes.len() - 1
check_block = (b: int, e: int, v: bool):
    print("check_block {b} {e} {v}")
    block_hook()
has_var = (t: int) -> bool: t == T_VAR
prune = (t: int) -> int: t
telem = (t: int) -> int: int(types[t].elem)
is_map_type = (t: int) -> bool: t == T_MAP or t == T_BAD_MAP
struct_targ = (si: int, i: int) -> int: if i == 0: T_STR else: T_INT
str_set_of = (t: int) -> int: if t == T_SET: 1 else if t >= 100: t - 100 else: 0
ntype = (n: int) -> int: int(nodes[n].type)
decl_in_prelude = (d: int) -> bool: prelude_decls.has(d)
exact_note = (n: int): print("exact_note {n}")
isolation_children = (k: NK) -> int:
    if k == .int_lit or k == .ident or k == .dotname or k == .bool_lit: return 0
    if k == .str_lit or k == .block or k == .tuple: return 16
    if k == .field or k == .not_ or k == .cast or k == .conv or k == .exprstmt: return 1
    if k == .binary or k == .and_ or k == .or_ or k == .assign: return 3
    if k == .if_: return 7
    if k == .vardecl: return 2
    if k == .array: return 18
    if k == .call or k == .intrinsic: return 17
    if k == .index: return 19
    -1
'''

DRIVER = r'''
use 'member_replay.jo'
fresh = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
ident = (name: int, pos: int) -> int:
    n = fresh(.ident, pos)
    nodes[n].name = i32(name)
    n
named = (k: NK, a: int, b: int) -> int:
    n = fresh(k, 1)
    nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
with_kids = (k: NK, a: int, items: int[]) -> int:
    n = fresh(k, 1)
    nodes[n].a = i32(a)
    set_list(n, items)
    n
call_named = (text: str, args: int[]) -> int: with_kids(.call, ident(intern(text), 2), args)
template = (dependent: int[]) -> MemberTemplate:
    t = MemberTemplate()
    loop d in dependent: t.dependent[d] = true
    t
show_template = (t: MemberTemplate) -> str:
    p = t.positions.keys(); p.sort()
    b = t.bindings.keys(); b.sort()
    "{t.body} {t.owner} pos={p} bind={b} texts={t.texts} locals={t.locals} requests={t.requests} refinements={t.refinements} okay={t.okay} decisions={t.decisions.len()} deps={t.dependent.len()} domain={t.domain.len()}"
syntax = (label: str, n: int, value: bool):
    t = MemberTemplate()
    member_dependencies(n, 90, mut t.dependent)
    print("{label}: {member_syntax(n, 90, mut t, value)} {show_template(t)}")
show_copy = (n: int, depth: int, tree: int):
    if n == 0: return
    x2 = nodes[n]
    print("{depth} {n - tree} k={x2.kind == .str_lit} sval={x2.sval} name={x2.name} aux={x2.aux} sym={x2.sym} kids={x2.nlist}")
    show_copy(int(x2.a), depth + 1, tree); show_copy(int(x2.b), depth + 1, tree); show_copy(int(x2.c), depth + 1, tree)
    loop i in [0..nkids(n)): show_copy(kid(n, i), depth + 1, tree)
main = ():
    name = 90
    loop nodes.len() < 100: nodes.push(Node())
    loop name_texts.len() < 100: name_texts.push("n{name_texts.len()}")
    check_scopes.top = fill(-1, 200)
    # Reset and its modes; the environment decides.
    member_record = 4
    member_reset()
    print("{member_record} {member_enabled} {member_trace} {member_templates.len()}")
    debug_vars = true
    member_reset()
    print(member_enabled)
    debug_vars = false
    member_reset()
    # Which subtrees mention the member name.
    x = ident(name, 7)
    y = ident(91, 8)
    pair = named(.binary, x, y)
    list = with_kids(.block, 0, [y, ident(92, 8)])
    four = fresh(.block, 1); nodes[four].c = i32(pair); nodes[four].d = i32(y)
    memo: {int: bool} = {}
    loop n in [0, x, y, pair, list, four, pair]: print("{member_dependencies(n, name, mut memo)} {memo.len()}")
    print("{member_dependent(pair, template([pair]))} {member_dependent(y, template([pair]))}")
    # Admission of every syntactic form.
    syntax("zero", 0, false)
    syntax("name", ident(name, 3), false)
    syntax("other", ident(60, 3), false)
    # (identifiers visible in scope, by what they hold)
    bind = (nm: int, kind: SK, r: int):
        syms.push(Sym(kind=kind, ref=i32(r)))
        check_scopes.syms.push(syms.len() - 1)
        check_scopes.top[nm] = check_scopes.syms.len() - 1
    local_of = (t: int, flags: int) -> int:
        locals.push(Local(type=i32(t), flags=i32(flags)))
        locals.len() - 1
    bind(61, .local, local_of(T_INT, 0))
    bind(62, .local, local_of(T_VAR, 0))
    loop f in [1, 4, 8, 16, 2]:
        bind(62 + f, .local, local_of(T_INT, f))
    globals.push(Global(type=i32(T_INT)))
    bind(80, .global, globals.len() - 1)
    globals.push(Global(type=i32(T_VAR)))
    bind(81, .global, globals.len() - 1)
    bind(82, .fns, 0)
    loop nm in [61, 62, 63, 66, 70, 78, 64, 80, 81, 82, 150, 199]: syntax("ident {nm}", ident(nm, 3), false)
    ctxs[0].floor = i32(check_scopes.syms.len())
    syntax("below floor", ident(62, 3), false)
    ctxs[0].floor = 0
    vd = (nm: int, a: int, b: int) -> int:
        n = fresh(.vardecl, 4)
        nodes[n].name = i32(nm); nodes[n].a = i32(a); nodes[n].b = i32(b)
        n
    syntax("decl", vd(60, 0, y), false)
    syntax("decl member", vd(name, 0, y), false)
    syntax("decl typed", vd(60, y, y), false)
    with_list = vd(60, 0, y); set_list(with_list, [y])
    syntax("decl kids", with_list, false)
    rd = vd(60, 0, y); nodes[rd].flags = 1
    syntax("decl readonly", rd, false)
    at_decl = vd(60, 0, y); nodes[at_decl].flags = 2
    syntax("decl at", at_decl, false)
    syntax("decl dependent", vd(60, 0, x), false)
    syntax("decl bytes", vd(60, 0, call_named("bytes", [ident(name, 3)])), false)
    syntax("decl call", vd(60, 0, call_named("other", [ident(name, 3)])), false)
    syntax("decl field call", vd(60, 0, with_kids(.call, named(.field, y, 0), [ident(name, 3)])), false)
    syntax("call bytes", named(.exprstmt, call_named("bytes", [y]), 0), false)
    syntax("call bytes value", call_named("bytes", [y]), true)
    syntax("call assert", named(.exprstmt, call_named("$assert", [y]), 0), false)
    syntax("call runtime", named(.exprstmt, call_named("$runtime_assert", [y]), 0), false)
    syntax("call dep assert", named(.exprstmt, call_named("$assert", [x]), 0), false)
    syntax("call other", named(.exprstmt, call_named("print", [y]), 0), false)
    push_callee = fresh(.field, 2); nodes[push_callee].a = i32(y); nodes[push_callee].name = i32(intern("push"))
    pop_callee = fresh(.field, 2); nodes[pop_callee].a = i32(y); nodes[pop_callee].name = i32(intern("pop"))
    syntax("push", named(.exprstmt, with_kids(.call, push_callee, [x]), 0), false)
    syntax("pop", named(.exprstmt, with_kids(.call, pop_callee, []), 0), false)
    syntax("computed callee", named(.exprstmt, with_kids(.call, fresh(.int_lit, 2), []), 0), false)
    syntax("stmt not call", named(.exprstmt, y, 0), false)
    syntax("stmt value", named(.exprstmt, y, 0), true)
    field_plain = fresh(.field, 1); nodes[field_plain].a = i32(y)
    field_b = named(.field, y, y)
    field_dep = fresh(.field, 1); nodes[field_dep].a = i32(x)
    syntax("field", field_plain, true); syntax("field b", field_b, true); syntax("field dep", field_dep, true)
    syntax("index", named(.index, y, x), true); syntax("index dep", named(.index, x, y), true)
    syntax("binary", named(.binary, y, y), true); syntax("binary dep", named(.binary, x, y), true)
    syntax("cast", named(.cast, y, 0), true); syntax("cast dep", named(.cast, x, 0), true)
    syntax("tname", fresh(.tname, 1), true); syntax("tname args", with_kids(.tname, 0, [y]), true)
    conditional = named(.if_, y, with_kids(.block, 0, [named(.exprstmt, y, 0)]))
    syntax("if", conditional, false)
    syntax("if dep", named(.if_, x, with_kids(.block, 0, [])), false)
    assign_index = named(.assign, named(.index, y, y), y); nodes[assign_index].op = i32(int(Tok.assign))
    assign_plus = named(.assign, named(.index, y, y), y); nodes[assign_plus].op = i32(int(Tok.pluseq))
    assign_var = named(.assign, y, y); nodes[assign_var].op = i32(int(Tok.assign))
    syntax("assign", assign_index, false); syntax("assign op", assign_plus, false); syntax("assign var", assign_var, false)
    loop k in [NK.block, NK.array, NK.and_, NK.or_, NK.not_, NK.int_lit, NK.str_lit, NK.bool_lit, NK.lambda, NK.match_]: syntax("kind", fresh(k, 1), true)
    tail_stmt = with_kids(.block, 0, [named(.exprstmt, y, 0), named(.exprstmt, call_named("bytes", [y]), 0)])
    syntax("block tail value", tail_stmt, true)
    syntax("block tail not", tail_stmt, false)
    extra2 = fresh(.block, 1); nodes[extra2].nlist2 = 1
    syntax("list2", extra2, true)
    fails = fresh(.block, 1); nodes[fails].a = i32(fresh(.lambda, 2))
    syntax("child a", fails, true)
    nodes[fails].a = 0; nodes[fails].b = i32(fresh(.lambda, 2))
    syntax("child b", fails, true)
    nodes[fails].b = 0; nodes[fails].c = i32(fresh(.lambda, 2))
    syntax("child c", fails, true)
    nodes[fails].c = 0; nodes[fails].d = i32(fresh(.lambda, 2))
    syntax("child d", fails, true)
    # Preparing a loop: every refusal, then a template.
    scope_of = (nm: int, text: str) -> int:
        s = fresh(.block, 5)
        sv = fresh(.str_lit, 5); nodes[sv].sval = i32(intern(text))
        nodes[s].a = i32(sv); nodes[s].name = i32(nm)
        s
    show_prepare = ():
        print("{member_templates.len()} {member_scopes.len()}")
        if member_templates.len() > 0: print(show_template(member_templates[member_templates.len() - 1]))
    good_body = () -> int:
        d = fresh(.vardecl, 4)
        nodes[d].name = 60; nodes[d].b = i32(call_named("bytes", [ident(name, 77)]))
        with_kids(.block, 0, [d])
    s1 = scope_of(name, "a"); s2 = scope_of(name, "b"); s3 = scope_of(name, "c")
    member_enabled_before = member_enabled
    member_enabled = false
    member_prepare([s1, s2], good_body())
    member_enabled = true
    member_prepare([s1], good_body())
    ide_on = true
    member_prepare([s1, s2], good_body())
    ide_on = false; cx = -1
    member_prepare([s1, s2], good_body())
    cx = 0; const_views = [1]
    member_prepare([s1, s2], good_body())
    const_views = []; sibling_known[1] = 1
    member_prepare([s1, s2], good_body())
    sibling_known.clear(); sibling_flow[1] = 1
    member_prepare([s1, s2], good_body())
    sibling_flow.clear()
    aux_scope = scope_of(name, "b"); nodes[aux_scope].aux = 1
    member_prepare([s1, aux_scope], good_body())
    bad_value = scope_of(name, "b"); nodes[bad_value].a = i32(fresh(.int_lit, 1))
    member_prepare([s1, bad_value], good_body())
    member_prepare([s1, s2], with_kids(.block, 0, [fresh(.lambda, 1)]))
    member_prepare([s1, s2], with_kids(.block, 0, [named(.exprstmt, call_named("bytes", [y]), 0)]))
    show_prepare()
    ctxs[0].inst = 3
    fns.push(FnInst()); fns.push(FnInst()); fns.push(FnInst()); fns.push(FnInst())
    member_prepare([s1, s2], good_body())
    show_prepare()
    # Candidates during a template's first check.
    prelude_decls[500] = true
    member_candidates([501])
    member_record = 0
    member_candidates([500])
    print(member_templates[0].okay)
    member_candidates([500, 501])
    print(member_templates[0].okay)
    member_templates[0].okay = true
    # Types that may share locals.
    loop t in [T_STR, T_INT, T_MATH_INT, T_BOOL, T_FLOAT, T_SET, T_INTS, T_MAP, T_BAD_MAP, T_OTHER, T_LOOP, T_VOID, T_INT]:
        print("{t} {member_plain(t)} {member_plain_types.len()}")
    # Domains, and a partial one.
    print("{member_domain_count(1)} {member_domain_count(1)} {member_domain_count(2)} {member_domain_count(3)} {member_domain_count(4)}")
    print("{member_words.len()} {member_words[3]["x"]} {member_words[2]["c"]} {member_templates[0].decisions.len()}")
    other_pos = fresh(.str_lit, 6)
    at_pos = fresh(.str_lit, 77)
    saved_record = member_record
    member_record = -1
    member_string_decision(at_pos, 1)
    member_record = saved_record
    member_string_decision(other_pos, 3)
    print(member_templates[0].okay)
    member_string_decision(at_pos, 4)
    print(member_templates[0].okay)
    member_string_decision(at_pos, 1)
    print(member_templates[0].okay)
    member_string_decision(at_pos, 3)
    print(member_templates[0].okay)
    member_templates[0].okay = true
    # Checked bodies.
    checked = (label: str, n: int):
        seen: {int: bool} = {}
        t = MemberTemplate()
        t.positions[77] = true
        t.texts = ["a", "b"]
        print("{label}: {member_checked(n, t, mut seen)} {seen.len()}")
    member_record = 0
    typed = (k: NK, pos: int, ty: int) -> int:
        n = fresh(k, pos)
        nodes[n].type = i32(ty)
        n
    checked("zero", 0)
    checked("str position", typed(.str_lit, 77, T_STR))
    checked("str position other", typed(.str_lit, 77, T_INT))
    checked("str elsewhere", typed(.str_lit, 3, T_INT))
    checked("dot none", typed(.dotname, 77, T_INT))
    checked("dot partial", typed(.dotname, 77, 104))
    checked("dot full", typed(.dotname, 77, 101))
    checked("dot elsewhere", typed(.dotname, 3, T_INT))
    ident_kind = (aux: int, l: int) -> int:
        n = fresh(.ident, 3)
        nodes[n].aux = i32(aux); nodes[n].sym = i32(l)
        n
    checked("global", ident_kind(2, 0))
    checked("fn ident", ident_kind(3, 0))
    loop lf in [1, 2, 4, 8, 16]: checked("local flag {lf}", ident_kind(1, local_of(T_INT, lf)))
    loop t in [T_STR, T_MATH_INT, T_OTHER, T_INT]: checked("local type {t}", ident_kind(1, local_of(t, 0)))
    loop k in [NK.lambda, NK.fnref, NK.partial, NK.narrow, NK.istype, NK.iflet, NK.match_, NK.for_, NK.while_, NK.return_, NK.tname]: checked("kind", fresh(k, 3))
    conv_of = (cv: CV) -> int:
        n = fresh(.conv, 3)
        nodes[n].aux = i32(int(cv))
        n
    loop cv in [CV.refinement, CV.set_text, CV.int_]: checked("conv", conv_of(cv))
    ms = fresh(.int_lit, 3); exact_stores[ms] = 1; checked("exact", ms)
    mr = fresh(.int_lit, 3); ref_narrowing[mr] = 1; checked("narrowing", mr)
    mw = fresh(.int_lit, 3); wi_fact_calls[mw] = 1; checked("warn", mw)
    checked("type var", typed(.int_lit, 3, T_VAR))
    intr = (i: IN) -> int:
        n = fresh(.intrinsic, 3)
        nodes[n].aux = i32(int(i))
        n
    loop i in [IN.to_bytes, IN.runtime_assert, IN.static_assert, IN.len, IN.push, IN.panic, IN.none_]: checked("intrinsic {int(i)}", intr(i))
    call_decl = (aux: int, decl: int, annotated: bool) -> int:
        fns.push(FnInst(decl=i32(decl)))
        n = fresh(.call, 3)
        nodes[n].aux = i32(aux); nodes[n].sym = i32(fns.len() - 1)
        if annotated: nodes[decl].c = 1
        n
    loop nodes.len() < 700: nodes.push(Node())
    prelude_decls[600] = true; prelude_decls[601] = true
    checked("call", call_decl(0, 600, false))
    checked("call aux", call_decl(1, 600, false))
    checked("call user", call_decl(0, 602, false))
    checked("call annotated", call_decl(0, 601, true))
    fanout = with_kids(.block, 0, [fresh(.int_lit, 3), fresh(.bool_lit, 3)])
    checked("block", fanout)
    checked("block fails", with_kids(.block, 0, [fresh(.lambda, 3)]))
    both = named(.binary, fresh(.int_lit, 3), fresh(.int_lit, 3))
    checked("binary", both)
    bad_a = named(.binary, fresh(.lambda, 3), fresh(.int_lit, 3))
    bad_b = named(.binary, fresh(.int_lit, 3), fresh(.lambda, 3))
    checked("bad a", bad_a); checked("bad b", bad_b)
    c_if = fresh(.if_, 3); nodes[c_if].c = i32(fresh(.lambda, 3))
    checked("bad c", c_if)
    shared = fresh(.int_lit, 3)
    checked("shared", with_kids(.block, 0, [shared, shared]))
    # Copies: literals at member positions, locals remapped, shared nodes once, divisors.
    t = MemberTemplate(owner=3)
    t.positions[88] = true
    member_words[101] = {"a": 5, "b": 6}
    lit_s = fresh(.str_lit, 88)
    lit_other = fresh(.str_lit, 89); nodes[lit_other].sval = 3
    dot = typed(.dotname, 88, 201)
    dot_other = typed(.dotname, 89, 201); nodes[dot_other].name = 44; nodes[dot_other].aux = 99
    l_old = local_of(T_INT, 0); l_unmapped = local_of(T_INT, 0)
    decl_node = fresh(.vardecl, 3); nodes[decl_node].sym = i32(l_old); nodes[decl_node].b = i32(fresh(.int_lit, 3))
    use_node = ident_kind(1, l_old); use_other = ident_kind(1, l_unmapped); global_use = ident_kind(2, l_old)
    fact_divisors[use_node] = 12
    sh = fresh(.int_lit, 3); nodes[sh].ival = 55
    cond = fresh(.if_, 3); nodes[cond].a = i32(sh); nodes[cond].b = i32(with_kids(.block, 0, [sh, lit_s])); nodes[cond].c = i32(with_kids(.block, 0, [dot, dot_other]))
    tree = with_kids(.block, 0, [decl_node, use_node, use_other, global_use, cond, lit_other])
    lm: {int: int} = {}
    lm[l_old] = 321
    nm: {int: int} = {}
    print("{member_copy(0, t, "a", lm, mut nm)} {nm.len()}")
    print(member_copy(tree, t, "a", lm, mut nm) - tree)
    print(nm.len())
    show_copy(nm[tree], 0, tree)
    # (a second member, sharing the template, gets its own nodes)
    nm2: {int: int} = {}
    show_copy(member_copy(tree, t, "b", lm, mut nm2), 0, tree)
    print(fact_divisors.len())
    print("copy ready")
    # Scope replay: unknown, refused (cloned), first check (template), then replay with obligations.
    print(member_scope(999))
    member_templates = [MemberTemplate(owner=3)]
    member_scopes[700] = 0
    loop nodes.len() < 705: nodes.push(Node())
    nodes[700].b = 701
    member_templates[0].okay = false
    print("{member_scope(700)} {nodes[700].b}")
    print("scopes ok")
'''

SCOPE_DRIVER = r'''
use 'member_replay.jo'
loc = (t: int, flags: int, name: int) -> int:
    locals.push(Local(type=i32(t), flags=i32(flags), name=i32(name)))
    locals.len() - 1
fresh = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
hook_locals: int[]
hook_requests: int[]
hook_refines: int[]
hook_other_owner = 0
hook_warns = 0
hook = ():
    loop l in hook_locals: fns[3].locals.push(l)
    loop r in hook_requests: fact_requests.push(FactRequest(r, 3))
    loop r in hook_refines: refine_requests.push(FactRequest(r, 3))
    if hook_other_owner != 0:
        fact_requests.push(FactRequest(hook_other_owner, 2))
        refine_requests.push(FactRequest(hook_other_owner, 2))
    loop i in [0..hook_warns): shown_warnings.push("w")
    member_candidates([999])
new_scope = (text: str, body: int, index: int) -> int:
    s = fresh(.block, 5)
    v = fresh(.str_lit, 5)
    nodes[v].sval = i32(intern(text))
    nodes[s].a = i32(v); nodes[s].b = i32(body)
    member_scopes[s] = index
    s
template_for = (bindings: int[], okay: bool) -> int:
    t = MemberTemplate(owner=3)
    loop b in bindings: t.bindings[b] = true
    t.okay = okay
    t.positions[88] = true
    member_templates.push(t)
    member_templates.len() - 1
show = (i: int):
    t = member_templates[i]
    print("t{i}: body={t.body != 0} locals={t.locals.len()} requests={t.requests.len()} refinements={t.refinements.len()} okay={t.okay}")
first = (label: str, index: int, body: int, ls: int[], requests: int[], refines: int[], other: int, warns: int):
    hook_locals = ls; hook_requests = requests; hook_refines = refines; hook_other_owner = other; hook_warns = warns
    s = new_scope("a", body, index)
    print("{label}: {member_scope(s)} record={member_record} {member_scope_locals.has(s)}")
    show(index)
main = ():
    block_hook = hook
    loop nodes.len() < 50: nodes.push(Node())
    fns = [FnInst(), FnInst(), FnInst(), FnInst()]
    member_reset()
    prelude_decls[999] = true
    block = () -> int:
        b = fresh(.block, 1)
        set_list(b, [fresh(.int_lit, 1)])
        b
    named_local = loc(T_INT, 0, 60)
    first("clean", template_for([60], true), block(), [named_local], [], [], 0, 0)
    first("unbound local", template_for([], true), block(), [loc(T_INT, 0, 60)], [], [], 0, 0)
    loop f in [1, 2, 4, 8, 16, 32]: first("flag {f}", template_for([60], true), block(), [loc(T_INT, f, 60)], [], [], 0, 0)
    loop ty in [T_VAR, T_STR, T_MATH_INT]: first("type {ty}", template_for([60], true), block(), [loc(ty, 0, 60)], [], [], 0, 0)
    with_const = loc(T_INT, 0, 60)
    locals[with_const].const_init = 5
    first("const init", template_for([60], true), block(), [with_const], [], [], 0, 0)
    first("unchecked", template_for([60], true), fresh(.lambda, 1), [], [], [], 0, 0)
    first("warned", template_for([60], true), block(), [], [], [], 0, 1)
    b2 = block()
    first("request seen", template_for([60], true), b2, [], [kid(b2, 0)], [], 0, 0)
    first("request unseen", template_for([60], true), block(), [], [fresh(.int_lit, 1)], [], 0, 0)
    b3 = block()
    first("refine seen", template_for([60], true), b3, [], [], [kid(b3, 0)], 0, 0)
    first("refine unseen", template_for([60], true), block(), [], [], [fresh(.int_lit, 1)], 0, 0)
    first("other owner", template_for([60], true), block(), [], [], [], fresh(.int_lit, 1), 0)
    # A replayed member: its own locals, literal and obligations, the first one's left untouched.
    hook_locals = []; hook_requests = []; hook_refines = []; hook_other_owner = 0; hook_warns = 0
    rl = loc(T_INT, 0, 61)
    copy_writes[rl] = 321
    lit_at = fresh(.str_lit, 88)
    nodes[lit_at].type = i32(T_STR)
    use_at = fresh(.ident, 3); nodes[use_at].aux = 1; nodes[use_at].sym = i32(rl); nodes[use_at].type = i32(T_INT)
    dead_request = fresh(.int_lit, 1)
    body = fresh(.block, 1)
    set_list(body, [lit_at, use_at])
    fact_divisors[use_at] = 7
    index = template_for([61], true)
    hook_locals = [rl]; hook_requests = [use_at]; hook_refines = [lit_at]
    first_scope = new_scope("a", body, index)
    print(member_scope(first_scope))
    show(index)
    member_templates[index].requests.push(dead_request)
    member_templates[index].refinements.push(dead_request)
    before_nodes = nodes.len()
    second = new_scope("b", 0, index)
    print(member_scope(second))
    copy_body = int(nodes[second].b)
    print("{copy_body >= before_nodes} {nkids(copy_body)} {name_of(int(nodes[kid(copy_body, 0)].sval))} {nodes[kid(copy_body, 1)].sym != i32(rl)} {copy_writes.len()} {fact_divisors.get(kid(copy_body, 1)) ?? -1}")
    print("{fact_requests.len()} {refine_requests.len()} {fns[3].locals.len()} {member_scope_locals[second].len()} {member_scope_locals[first_scope].len()}")
    print(fact_requests[fact_requests.len() - 1].owner)
    print(locals[member_scope_locals[second][0]].name)
    print("replay ok")
'''


@pytest.mark.parametrize('driver, mode, release', [(DRIVER, '', False), (DRIVER, 'trace', False), (DRIVER, 'reference', False), (DRIVER, '', True), (SCOPE_DRIVER, 'trace', False), (SCOPE_DRIVER, '', True)],
                         ids=['default', 'trace', 'reference', 'release', 'scope-trace', 'scope-release'])
def test_member_admit_twins(compiler, tmp_path, monkeypatch, driver, mode, release):  # noqa: F811
    monkeypatch.setenv('DEWY_MEMBERS', mode)
    state = (ROOT / 'compiler/member_replay.jo').read_text()
    state = state[state.index('struct MemberTemplate'):]
    output = compare_narrow(compiler, tmp_path, release,
                            ('checker_tokens', 'node_store', 'checker_types', 'checker_state', 'refinement_types', 'member_admit'), driver,
                            doubles={'services.jo': SERVICES, 'member_replay.jo': "use 'services.jo'\n" + state},
                            services=('ast', 'check', 'exact', 'expr', 'facts', 'ide', 'isolation', 'isolation_ops', 'main', 'lex', 'refine', 'reflection', 'sibling_types', 'types', 'util', 'warn_if'))
    assert output.endswith(b'scopes ok\n') or b'true 2 b true' in output and output.endswith(b'replay ok\n')
