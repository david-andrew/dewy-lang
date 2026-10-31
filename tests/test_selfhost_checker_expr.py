"""The expression dispatcher: checked nodes, name lookup and kind routing match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_idents import DRIVER as IDENTS
from tests.test_selfhost_checker_resolve import compare

STEMS = ('checker_exact', 'checker_literals', 'checker_idents', 'checker_conditionals', 'checker_members',
         'checker_indexes', 'checker_receivers', 'checker_variants', 'checker_type_apply',
         'checker_unary', 'checker_logic', 'checker_type_tests', 'checker_optional',
         'checker_aggregates', 'checker_collections', 'checker_cast', 'checker_places',
         'checker_in_range', 'checker_numeric', 'checker_expr')

DRIVER = IDENTS + r'''
syms: Sym[] = [Sym()]
xe_scope = CheckerScope()
xe_at: int[]
xe_mods: int[]
xe_found: int[]
xe_ticks: int[]
xe_struct = 1
xe_sentinel_name = 0
xe_temperature_on = false
xe_values_on = false
xe_watch_counts = StatementWatch()
xe_checked = 0
xe_module_result = 0
xe_grow = false
xe_complete_host = (): events.push("complete")
xe_unknown_host = (n: int, expected: int, name: int):
    print(events)
    print("unknown:{n}:{expected}:{name}")
    exit(19)
xe_module_host = (m: int, name: int) -> int:
    events.push("module:{m}:{name}")
    xe_module_result
xe_temperature_host = (n: int, t: int) -> int:
    events.push("temperature:{n}:{t}")
    T_FLOAT
xe_values_host = (n: int, t: int): events.push("values:{n}:{t}")
xe_set_answer = false
xe_context_answer = false
xe_dotted_host = (n: int, expected: int) -> int:
    events.push("dotted:{n}:{expected}")
    T_FLOAT
xe_juxt_host = (n: int): events.push("juxt:{n}")
xe_char_host = (n: int): events.push("char:{n}")
xe_member_host = (n: int, expected: int) -> int:
    events.push("member:{n}:{expected}")
    T_BOOL
xe_quantity_hint_host = (t: int) -> int:
    events.push("quantity-hint:{t}")
    T_F32
xe_decimal_host = (e: int): events.push("decimal:{e}")
xe_set_host = (e: int) -> bool:
    events.push("set:{e}")
    xe_set_answer
xe_context_host = (e: int, t: int, op: int) -> bool:
    events.push("context:{e}:{t}:{op}")
    xe_context_answer
xe_nd_host = (n: int, t: int, h: int) -> int:
    events.push("nd:{n}:{t}:{h}")
    T_U8
xe_secret_host = (n: int, a: int, b: int) -> int:
    events.push("secret:{n}:{a}:{b}")
    T_BOOL
xe_rest_host = (n: int, expected: int, a: int, b: int, ta: int, tb: int, hint: int, flags: int) -> int:
    events.push("rest:{n}:{expected}:{a}:{b}:{ta}:{tb}:{hint}:{flags}")
    if xe_grow:
        xe_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); syms.push(Sym())
        check_expr(node(.int_lit), 0)
    T_FLOAT
xe_num_coerce = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xe_num_potential = (n: int) -> bool:
    events.push("potential:{n}")
    false
xe_num_numjoin = (a: int, b: int) -> int: 0
xe_num_join = (a: int, b: int, pos: int) -> int:
    events.push("join:{a}:{b}")
    int(nodes[a].type)
xe_num_exact = (n: int) -> int: T_MATH_INT
xe_num_library = (pos: int) -> bool: false
xe_num_nan = (v: f64) -> f64: v
xe_num_division = (n: int, x: int, y: int): events.push("division:{n}")
xe_num_percent = (n: int, a: int): events.push("percent:{n}")
xe_num_error = (n: int, code: int):
    print(events)
    print("numeric-error:{n}:{code}")
    exit(19)
xe_num_services = CheckerNumericHost(xe_num_coerce, xe_num_potential, xe_num_numjoin, xe_num_join, xe_num_exact, xe_num_library, xe_num_nan, xe_num_division, xe_num_percent, xe_num_error)
xe_num_inputs = CheckerNumericInput(&nodes, &types, &files, &T_INT, &T_MATH_INT, &T_U64, &T_FLOAT, &T_BOOL, &T_NEVER, &xe_num_services)
xe_num_binding = checker_numeric_bind(&xe_num_inputs)
xe_right_at = 0
xe_call_host = (n: int, expected: int) -> int:
    events.push("call:{n}:{expected}")
    T_STR
xe_sibling_host = (n: int, t: int) -> int:
    events.push("sibling:{n}:{t}")
    t
xe_literal_host = (n: int, expected: int, ex: int) -> int:
    events.push("literal:{n}:{expected}:{ex}")
    ex
xe_other_host = (n: int, expected: int) -> int:
    events.push("other:{n}:{int(nodes[n].kind)}:{expected}")
    T_BOOL
xe_services = CheckerExprHost(xe_complete_host, xe_unknown_host, xe_module_host, xe_temperature_host, xe_values_host, xe_dotted_host, xe_juxt_host, xe_char_host, xe_member_host, xe_quantity_hint_host, xe_decimal_host, xe_set_host, xe_context_host, xe_nd_host, xe_secret_host, xe_rest_host, xe_call_host, xe_sibling_host, xe_literal_host, xe_other_host)
xe_inputs = CheckerExprInput(&nodes, &types, &files, &syms, &xe_scope, &ctxs, &cx, &xe_at, &xe_mods, &xe_found, &xe_ticks, &xe_struct, &xe_sentinel_name, &xe_temperature_on, &xe_values_on, &xe_watch_counts, &xe_checked, &T_BOOL, &T_INT, &T_U64, &T_MATH_INT, &xe_right_at, &xe_services)
xe_binding = checker_expr_bind(&xe_inputs)
sym_of = (kind: SK, ref: int) -> int:
    syms.push(Sym(name = 2, kind = kind, ref = i32(ref)))
    syms.len() - 1
# Name 2 bound in scope at index i, to symbol s.
scoped = (s: int, at: int):
    loop xe_scope.syms.len() <= at: xe_scope.syms.push(0)
    xe_scope.syms[at] = s
    loop xe_scope.top.len() <= 2: xe_scope.top.push(-1)
    xe_scope.top[2] = at
cached = (m: int, s: int, stamp: int):
    loop xe_at.len() <= 2: xe_at.push(0); xe_mods.push(0); xe_found.push(0)
    xe_at[2] = stamp; xe_mods[2] = m; xe_found[2] = s
show = (n: int, expected: int = 0):
    t = check_expr(n, expected)
    print("{n}:{t}:{xe_checked}:{int(nodes[n].kind)}:{nodes[n].type}:{nodes[n].aux}:{nodes[n].sym}:{int(nodes[n].flags)}")
# Binary operators: rare heads on the host, operands here, plain numbers in the numeric leaf.
binaries = ():
    show(binop(.dotop, done(T_INT), done(T_INT)), T_INT)
    j = binop(.star, done(T_INT), done(T_INT)); nodes[j].flags = i32(536870912); show(j)
    show(binop(.kw_xor, done(T_BOOL), done(T_BOOL)))
    show(binop(.kw_xor, done(T_INT), done(T_INT)))
    show(binop(.eq, done(T_STR, .str_lit, 512), done(T_INT)))
    show(binop(.eq, done(T_STR, .str_lit, 512), done(T_STR)))
    show(binop(.eq, done(T_STR, .str_lit, 512), done(T_STR, .str_lit, 512)))
    show(binop(.kw_in, done(T_INT), done(T_INT)))
    # Plain numbers, hints from the expected type, literals, comparisons.
    show(binop(.amp, done(T_INT), done(T_INT)), T_INT)
    loop op in [Tok.plus, Tok.minus, Tok.star, Tok.lt, Tok.eq, Tok.shl, Tok.percent]:
        show(binop(op, done(T_INT), done(T_INT)), T_INT)
        show(binop(op, done(T_FLOAT), done(T_FLOAT)))
        show(binop(op, done(T_INT, .int_lit, 256), done(T_INT, .int_lit, 256)))
        show(binop(op, done(T_INT), done(T_STR)), T_FLOAT)
    q = types.len(); types.push(TypeInfo(kind = .quantity))
    show(binop(.plus, done(T_INT), done(T_INT)), q)
    show(binop(.lt, done(T_INT), done(T_INT)), q)
    show(binop(.plus, done(T_INT), done(T_INT)), T_VEC2)
    show(binop(.eq, done(T_FLOAT), done(T_FLOAT)))
    show(binop(.lt, done(T_INT, .binary), fresh(.int_lit)))
    show(binop(.lt, done(T_INT, .binary), fresh(.int_lit, 2097152)))
    show(binop(.plus, done(T_FLOAT, .float_lit), done(T_FLOAT)))
    show(binop(.plus, done(T_INT), done(T_INT), false))
    # Decimal reads compared, quantity syntax, characters.
    xe_watch_counts.decimal_adapted = 1
    show(binop(.eq, done(T_INT), done(T_INT)))
    show(binop(.lt, done(T_INT), done(T_INT)))
    xe_watch_counts.decimal_adapted = 0
    lit2 = fresh(.int_lit)
    m = name_node(); nodes[m].pos = (1 << 40) + m
    scaled = binop(.star, lit2, m)
    show(binop(.plus, scaled, done(T_INT)), T_INT)
    m2 = name_node()
    show(binop(.star, fresh(.int_lit), m2), T_INT)
    right = done(T_INT)
    xe_right_at = right
    show(binop(.minus, done(T_INT), right))
    xe_right_at = 0
    show(binop(.star, done(T_STR, .str_lit, 512), done(T_INT)))
    show(binop(.plus, done(T_STR, .str_lit, 512 | 8), done(T_INT)))
    show(binop(.plus, done(T_STR, .str_lit, 512 | 8), done(T_STR, .str_lit, 512)))
    show(binop(.plus, done(T_INT), done(T_STR, .str_lit, 512)))
    # Literal operands take the other side's type; set literals ask the host.
    show(binop(.eq, done(T_INT, .array), done(T_INT)))
    xe_context_answer = true
    show(binop(.eq, done(T_INT, .array), done(int(tb_mk_opt(T_INT)))))
    show(binop(.ne, done(T_INT), done(T_INT, .record_lit)))
    show(binop(.minus, done(T_INT, .map_lit), done(T_INT, .map_lit)))
    show(binop(.eq, done(T_INT, .array), done(T_INT), false))
    callee = done(T_INT)
    c = done(0, .call); nodes[c].flags = 0; nodes[c].a = i32(callee); node_set_list(mut nodes, mut lists, c, [done(T_INT)])
    xe_set_answer = true
    show(binop(.amp, c, done(T_INT)))
    xe_context_answer = false
    xe_set_answer = false
    # Arrays written out against n-dimensional values; secrets; exact word operands.
    st = types.len(); types.push(TypeInfo(kind = .struct_))
    show(binop(.star, done(st), done(T_INT, .array)))
    show(binop(.lt, done(st), done(T_INT, .array)))
    sec = int(tb_mk_secret(T_INT))
    show(binop(.lt, done(sec), done(T_INT)))
    show(binop(.lt, done(T_INT), done(sec)))
    word = done(T_INT)
    wrap = done(T_MATH_INT, .conv); nodes[wrap].aux = 1; nodes[wrap].a = i32(word)
    show(binop(.plus, wrap, done(T_INT)))
    show(binop(.plus, wrap, done(T_INT), false))
    show(binop(.lt, done(T_MATH_INT, .int_lit, 256), done(T_INT)))
    show(binop(.plus, done(T_MATH_INT), done(T_MATH_INT)))
    show(binop(.shl, done(T_INT), done(T_INT)))
prepare_expr = ():
    prepare_idents()
    files.push(SrcFile(is_dewy = true))
# An operand already checked as t (kind k, flags added); in a Dewy file when dewy.
done = (t: int, k: NK = .ident, flags: int = 0, dewy: bool = true) -> int:
    n = node(k); nodes[n].type = i32(t); nodes[n].flags = i32(128 | flags)
    if dewy: nodes[n].pos = (1 << 40) + n
    n
binop = (op: Tok, a: int, b: int, dewy: bool = true) -> int:
    n = node(.binary, a); nodes[n].b = i32(b); nodes[n].op = i32(int(op))
    if dewy: nodes[n].pos = (1 << 40) + n
    n
# An unchecked operand outside Dewy (an integer literal there is typed int).
fresh = (k: NK, flags: int = 0) -> int:
    n = node(k); nodes[n].flags = i32(flags); n
'''

MAIN = r'''
main = ():
    prepare_expr()
    own = local_of(T_INT, 1)
    # A checked node keeps its type; an unchecked one is routed by kind.
    n = node(.binary); nodes[n].type = i32(T_U8); nodes[n].flags = 128
    show(n)
    show(node(.call), T_INT)
    show(node(.int_lit))
    show(node(.int_lit), T_FLOAT)
    show(node(.bool_lit))
    show(node(.float_lit), T_FLOAT)
    show(node(.str_lit))
    loop k in [NK.lambda, NK.block, NK.match_, NK.range, NK.propagate, NK.intrinsic, NK.vardecl]: show(node(k), T_INT)
    # Binary checking may grow every arena and reenter before the result is published.
    xe_grow = true
    n = binop(.plus, done(T_STR), done(T_STR))
    show(n, T_INT)
    assert(not xe_grow and nodes[n].type == i32(T_FLOAT))
    # Names: the scope above the function's floor, else the module cache, else the host.
    scoped(sym_of(.local, own), 4)
    show(name_node())
    ctxs[cx].floor = 5
    g = sym_of(.local, own)
    cached(int(ctxs[cx].mod), g, 1)
    show(name_node())
    xe_ticks = [0, 0, 7]
    xe_module_result = g
    show(name_node())
    xe_at[2] = 7
    show(name_node())
    xe_mods[2] = 5
    show(name_node())
    xe_mods[2] = int(ctxs[cx].mod)
    xe_ticks = [0, 0, 0]
    xe_struct = 7
    show(name_node())
    # Outside every function: no floor, the module -1; a module name, which reads no context.
    cx = -1
    xe_mods[2] = -1
    xe_found[2] = sym_of(.module, 0)
    xe_scope.top[2] = -1
    show(name_node())
    cx = 1
    ctxs[cx].floor = 0
    # Every symbol kind reaches the identifier leaf with its frozen ordinal.
    loop k in [SK.global, SK.fns, SK.struct_, SK.enum_, SK.const_, SK.module, SK.type_, SK.alias_]:
        globals.push(Global(type = i32(T_INT), state = 2))
        scoped(sym_of(k, globals.len() - 1), 4)
        show(name_node(), T_INT)
    # Rare tables, completion, temperatures and several values.
    scoped(sym_of(.local, own), 4)
    xe_watch_counts.const_views = 1
    xe_watch_counts.decimal_globals = 2
    show(name_node())
    xe_watch_counts.const_views = 0
    xe_watch_counts.decimal_globals = 0
    xe_sentinel_name = 2
    show(name_node())
    xe_sentinel_name = 3
    show(name_node())
    xe_temperature_on = true
    xe_values_on = true
    show(name_node())
    xe_temperature_on = false
    xe_values_on = false
    binaries()
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_expr_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS).endswith(b'ok\n')


@pytest.mark.parametrize('setup', ['xe_module_result = 0', 'ctxs[cx].floor = 9'])
def test_checker_expr_unknown_names(compiler, tmp_path, setup):  # noqa: F811
    main = f'''
main = ():
    prepare_expr()
    scoped(sym_of(.local, local_of(T_INT, 1)), 4)
    {setup}
    if ctxs[cx].floor == 0: xe_scope.top[2] = -1
    show(name_node())
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS)
    assert b'unknown:' in output and b'module:' in output
