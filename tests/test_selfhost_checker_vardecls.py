"""Declarations: forms, values, inferred and written types, flags and per-binding tables match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_loops import DRIVER as LOOPS
from tests.selfhost_expr_double import compare_leaf

STEMS = ('checker_loops', 'checker_vardecls')
DRIVER = LOOPS + r'''
locals: Local[] = [Local()]
dv_refining = false
dv_effects = false
dv_ide = false
dv_literals: {int: bool} = {}
dv_pending: int[]
dv_block = 0
dv_index = 0
dv_flow_next = 0
dv_flow_local = 0
dv_parents: {int: int} = {}
dv_quat_nodes: {int: bool} = {}
dv_quat_locals: {int: bool} = {}
dv_tk: {int: int} = {}
dv_watch = StatementWatch()
dv_cached = 0
dv_growth_pending = 0
dv_whole = false
dv_forms: {int: bool} = {}
dv_syntax = 0
dv_literal_type = 0
dv_value_type = 0
dv_grow_once = false
dv_form = (s: int, code: int) -> bool:
    events.push("form:{s}:{code}")
    dv_forms.get(code) ?? false
dv_binding_type = (s: int) -> int:
    events.push("type:{s}")
    int(nodes[int(nodes[s].a)].type)
dv_default = (t: int, pos: int) -> int:
    events.push("default:{t}:{pos}")
    typed(.call, t)
dv_syntax_type = (n: int) -> int:
    events.push("syntax:{n}")
    dv_syntax
dv_values = (n: int, expected: int) -> int:
    events.push("values:{n}:{expected}")
    if dv_grow_once:
        dv_grow_once = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); locals.push(Local()); structs.push(StructInfo())
    last = n
    if dv_value_type != 0: return dv_value_type
    int(nodes[n].type)
dv_annotated = (s: int, t: int, m: int): events.push("annotated:{s}:{t}:{m}")
dv_coerce = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    n
dv_sibling = (s: int, t: int, code: int) -> int:
    events.push("sibling:{s}:{t}:{code}")
    t
dv_literal = (s: int) -> int:
    events.push("literal:{s}")
    dv_literal_type
dv_storage = (s: int, t: int) -> int:
    events.push("storage:{s}:{t}")
    t
dv_value_param = (s: int, t: int) -> int:
    events.push("value-param:{s}:{t}")
    t
dv_temperature = (s: int, t: int, unit: int) -> int:
    events.push("temperature:{s}:{t}:{unit}")
    t
dv_binding = (name: int, t: int, pos: int) -> int:
    events.push("binding:{name}:{t}:{pos}")
    locals.push(Local(name = i32(name), type = i32(t)))
    locals.len() - 1
dv_pattern_type = 0
dv_pattern_global = 0
dv_pattern_fail = false
# (1 a global pattern's answer, 2 the unpacked type, 3 a shape refusal when told to fail,
# 4 an element alias's value as checked)
dv_pattern = (s: int, t: int, code: int) -> int:
    events.push("pattern:{s}:{t}:{code}")
    if code == 1: return dv_pattern_global
    if code == 2: return if dv_pattern_type != 0: dv_pattern_type else: int(nodes[int(nodes[s].b)].type)
    if code == 3 and dv_pattern_fail:
        print(events)
        print("error:{s}:{t}:3")
        exit(19)
    if code == 4: return int(nodes[s].b)
    0
dv_after = (s: int, l: int, t: int, code: int): events.push("after:{s}:{l}:{t}:{code}")
dv_error = (s: int, t: int, code: int):
    print(events)
    print("error:{s}:{t}:{code}")
    exit(19)
dv_services = CheckerDeclHost(dv_form, dv_binding_type, dv_default, dv_syntax_type, dv_values, dv_annotated, dv_coerce, dv_sibling, dv_literal, dv_storage, dv_value_param, dv_temperature, dv_binding, dv_pattern, dv_after, dv_error)
dv_inputs = CheckerDeclInput(&nodes, &lists, &types, &structs, &files, &locals, &ctxs, &cx, &last, &dv_refining, &dv_effects, &dv_ide, &dv_literals, &dv_pending, &dv_block, &dv_index, &dv_flow_next, &dv_flow_local, &dv_parents, &dv_quat_nodes, &dv_quat_locals, &dv_tk, &dv_watch, &dv_cached, &dv_growth_pending, &dv_whole, &T_STR, &T_MATH_INT, &dv_services)
dv_bound = checker_vardecls_bind(&dv_inputs)
DEWY = 1 << 40
# let name[:tn] = value (flags on the declaration)
decl = (name: int, value: int, tn: int = 0, flags: int = 0, dewy: bool = true) -> int:
    s = node(.vardecl, tn)
    nodes[s].b = i32(value)
    nodes[s].name = i32(name)
    nodes[s].flags = i32(flags)
    if dewy: nodes[s].pos = DEWY + s
    s
lit = (k: NK, t: int) -> int:
    n = typed(k, t); nodes[n].flags = i32(256); n
mk_type = (k: TK) -> int:
    types.push(TypeInfo(kind = k)); types.len() - 1
run = (s: int):
    vd_decl(s)
    l = int(nodes[s].sym)
    print("{s}:{nodes[s].kind}:{nodes[s].b}:{l}:{locals[l].type}:{locals[l].flags}:{locals[l].const_init}:{dv_flow_local}:{dv_whole}")
    print("  {events}")
    events = []
prepare_decls = ():
    prepare_loops()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_decls()
    rec = mk_type(.struct_)
    structs.push(StructInfo(name = "Shape", union_ = true))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1))); shape = types.len() - 1
    tup = mk_type(.tuple)
    # Inferred: a literal's default (an integer domain), a value, text, a record.
    dv_literal_type = T_MATH_INT
    run(decl(11, lit(.int_lit, T_INT)))
    dv_literal_type = T_INT
    run(decl(11, lit(.float_lit, T_INT)))
    run(decl(12, typed(.ident, T_STR)))
    run(decl(12, typed(.ident, T_STR), 0, 0, false))
    dv_grow_once = true
    run(decl(13, typed(.call, rec)))
    # Written types, with and without values; unions followed; defaults; refinements.
    run(decl(14, typed(.ident, T_INT), typed(.tname, T_I32)))
    run(decl(14, 0, typed(.tname, T_I32)))
    dv_forms[9] = true
    run(decl(14, 0, typed(.tname, T_I32)))
    run(decl(14, 0, typed(.tname, T_I32), 262144))
    dv_forms[9] = false
    dv_refining = true
    refined = mk_type(.refined)
    run(decl(14, 0, typed(.tname, refined)))
    dv_refining = false
    run(decl(15, typed(.call, rec), typed(.tname, shape)))
    dv_syntax = rec
    run(decl(15, typed(.call, T_INT), typed(.tname, shape)))
    dv_syntax = 0
    run(decl(15, typed(.call, T_INT), typed(.tname, shape), 0, false))
    # Siblings: a tuple of sibling literals, a record later given a sibling.
    v = typed(.tuple, tup); dv_literals[v] = true
    run(decl(16, v))
    blk = node(.block)
    d = decl(16, typed(.call, rec))
    node_set_list(mut nodes, mut lists, blk, [d, node(.exprstmt)])
    dv_block = blk; dv_index = 0
    run(d)
    dv_parents[rec] = 9
    run(d)
    dv_index = 1
    run(d)
    dv_block = 0
    dv_pending.push(rec); dv_flow_next = 1
    run(decl(17, typed(.ident, T_INT)))
    dv_pending = []; dv_flow_next = 0; dv_flow_local = 0
    # Temperatures, decimals, growth, quaternions.
    mul = node(.binary, lit(.int_lit, T_INT)); nodes[mul].op = 60; nodes[mul].b = i32(node(.ident)); nodes[int(nodes[mul].b)].name = 4; nodes[mul].type = i32(T_INT)
    run(decl(18, mul))
    neg = node(.unary, mul); nodes[neg].op = 59; nodes[neg].type = i32(T_INT)
    run(decl(18, neg))
    dv_literal_type = rec
    run(decl(19, lit(.float_lit, rec)))
    dv_literal_type = T_INT
    dv_watch.decimal_adapted = 1
    run(decl(19, lit(.int_lit, T_INT)))
    dv_growth_pending = 1
    run(decl(20, typed(.ident, T_INT)))
    dv_growth_pending = 0
    ctxs[cx].loop_depth = 1
    run(decl(20, typed(.ident, T_INT)))
    dv_watch.growth = 1
    run(decl(20, typed(.ident, T_INT)))
    run(decl(20, typed(.ident, T_INT), typed(.tname, T_INT)))
    ctxs[cx].loop_depth = 0
    q = typed(.call, rec); dv_quat_nodes[q] = true; dv_watch.quaternions = 1
    run(decl(21, q))
    # Flags: constants, loop counts, value parameters; effects and the editor.
    run(decl(22, typed(.ident, T_INT), 0, 262144))
    run(decl(22, typed(.ident, T_INT), 0, 33554432))
    vp = decl(22, typed(.ident, T_INT)); nodes[vp].aux2 = 1
    run(vp)
    dv_refining = true
    vp = decl(22, typed(.ident, T_INT)); nodes[vp].aux2 = 1
    run(vp)
    dv_refining = false
    dv_effects = true; dv_ide = true
    run(decl(23, typed(.ident, T_INT)))
    run(decl(23, typed(.ident, T_INT), typed(.tname, T_INT)))
    dv_effects = false; dv_ide = false
    # The forms other services declare, and those they pass back.
    spawn = typed(.call, T_INT); nodes[spawn].aux2 = 17
    run(decl(24, spawn))
    run(decl(24, typed(.ident, T_INT), 0, 131072))
    run(decl(24, typed(.ident, T_INT), 0, 8388608))
    lent = typed(.call, T_INT); nodes[lent].aux2 = -11
    run(decl(24, lent))
    dv_forms[4] = true
    run(decl(24, lent))
    run(decl(24, node(.propagate, lent)))
    dv_forms[4] = false
    place = typed(.index, T_INT); nodes[place].flags = 1
    run(decl(24, place))
    run(decl(24, place, 0, 0, false))
    dv_forms[5] = true
    run(decl(24, place))
    dv_forms[5] = false
    shaped = typed(.tarray, T_INT); nodes[shaped].ival = 1
    run(decl(24, typed(.ident, T_INT), shaped))
    pattern = decl(24, typed(.ident, tup))
    node_set_list(mut nodes, mut lists, pattern, [node(.hole)])
    run(pattern)
    run(decl(24, typed(.ident, T_INT), 0, 2048))
    # Patterns: names bound to elements (constants, value parameters), discards, globals;
    # element aliases.
    dv_pattern_type = int(tb_mk_tuple([T_INT, T_STR, T_I32]))
    loop flags in [0, 262144, 2048]:
        pattern = decl(25, typed(.call, T_INT), 0, flags)
        a = node(.ident); nodes[a].name = 26; nodes[a].pos = 7
        c = node(.ident); nodes[c].name = 27; nodes[c].pos = 9
        node_set_list(mut nodes, mut lists, pattern, [a, node(.hole), c])
        if flags == 0: nodes[pattern].aux2 = 1
        run(pattern)
        print("  {nodes[a].sym}:{locals[int(nodes[a].sym)].flags}:{locals[int(nodes[a].sym)].type}:{nodes[c].sym}:{locals[int(nodes[c].sym)].flags}:{locals[int(nodes[c].sym)].type}:{nodes[pattern].type}")
    dv_pattern_global = 1
    run(pattern)
    dv_pattern_global = 0
    dv_pattern_type = 0
    alias = decl(28, typed(.index, T_I32), 0, 8388608)
    run(alias)
    print("  {locals.len()}:{locals[locals.len() - 1].flags}:{locals[locals.len() - 1].alias}:{locals[locals.len() - 1].type}:{nodes[alias].nlist}")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_vardecls_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare_leaf(compiler, tmp_path, release, DRIVER + MAIN, 'xb_check', extra_stems=STEMS).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('dv_literal_type = mk_type(.none_lit); run(decl(11, lit(.int_lit, T_INT)))', 1),
    ('run(decl(11, 0))', 2),
    ('run(decl(11, typed(.call, T_VOID)))', 3),
    ('run(decl(11, typed(.ident, mk_type(.null_))))', 4),
    ('run(decl(11, typed(.ident, mk_type(.typeval))))', 5),
    ('run(decl(11, typed(.ident, mk_type(.module))))', 5),
    ('dv_pattern_fail = true; p = decl(11, typed(.ident, T_INT)); node_set_list(mut nodes, mut lists, p, [node(.ident)]); run(p)', 3),
])
def test_checker_vardecls_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_decls()
    {case}
    print("unreachable")
'''
    output = compare_leaf(compiler, tmp_path, False, DRIVER + main, 'xb_check', status=19, extra_stems=STEMS)
    assert output.rstrip().endswith(f':{code}'.encode())
