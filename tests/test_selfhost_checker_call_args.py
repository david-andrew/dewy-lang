"""check_args_untyped: argument literal shapes, function-value marks and the checks of
settled arguments before an overload is picked match frozen Jo; so do values_settled's
answers (a call with nothing to expand)."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_expr import DRIVER as EXPR, JO_DOUBLES, STEMS

DRIVER = EXPR + r'''
cq_names: int[] = [0]
cq_set = 9
cq_order_host = (n: int, given: int[], final: int[]): events.push("order:{n}")
cq_overlap_host = (args: int[], mask: int, pos: int): events.push("overlap:{mask}")
cq_float_host = (n: int): events.push("float:{n}")
cq_float_names: int[] = [0, 0, 0, 0]
cq_habit_host = (n: int, name: int, args: int[]): events.push("habit:{n}")
cq_host = CheckerCallQueryHost(cq_order_host, cq_overlap_host, cq_float_host, cq_habit_host)
cq_family: int[]
cq_input = CheckerCallQueryInput(&nodes, &lists, &files, &cq_names, &cq_set, &fns, &cq_float_names, &cq_host, &syms, &names, &cq_family, &cq_family, &cq_family, &cq_family, &cq_family, &cq_family)
cq_binding = checker_call_queries_bind(&cq_input)
cz_members = 0
cz_members_host = (n: int):
    events.push("members:{n}")
    if cz_members == 0: cz_members = 5
    if nodes[int(nodes[n].a)].name == 5: nodes[n].kind = .array
cz_spread_host = (n: int):
    events.push("spread:{n}")
    nodes[n].kind = .record_lit
cz_host = CheckerCallHost(cz_members_host, cz_spread_host)
cz_marks: bool[]
cz_input = CheckerCallInput(&lists, &locals, &cz_members, &cq_set, &cz_host, &names, &cz_marks, &cz_marks, &fns)
cz_binding = checker_call_bind(&cz_input)
# An unchecked node of kind k with children, in a Dewy file.
raw = (k: NK, children: int[] = [], a: int = 0) -> int:
    n = node(k, a, 0, 0, children); nodes[n].pos = (1 << 40) + n; n
named = (name: int) -> int:
    n = raw(.ident); nodes[n].name = i32(name); n
bind = (name: int, s: int):
    loop xe_scope.syms.len() <= 10 + name: xe_scope.syms.push(0)
    xe_scope.syms[10 + name] = s
    loop xe_scope.top.len() <= name: xe_scope.top.push(-1)
    xe_scope.top[name] = 10 + name
show_all = (label: str, ns: int[]):
    loop n in ns: print("{label}:{n}:{int(nodes[n].kind)}:{nodes[n].type}:{int(nodes[n].flags)}")
'''

MAIN = r'''
main = ():
    prepare_expr()
    # (call names checked through check_call_expr are spelled)
    loop names.len() < 32: names.push("f{names.len()}")
    files.push(SrcFile(is_dewy = false))
    fn_t = int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, false))
    bind(2, sym_of(.local, local_of(T_INT, 1)))
    bind(3, sym_of(.fns, 0))
    bind(4, sym_of(.local, local_of(fn_t, 1)))
    mod_sym = sym_of(.module, 6)
    bind(6, mod_sym)
    xe_module_result = sym_of(.fns, 0)
    # Plain values are checked and marked; holes and named functions are not.
    plain = named(2)
    lit = raw(.int_lit)
    wrapped = raw(.namedarg, [], lit)
    fn_name = named(3)
    fn_local = named(4)
    mut_local = named(4); nodes[mut_local].flags = 1
    jo_local = named(4); nodes[jo_local].pos = (2 << 40) + jo_local
    hole = raw(.hole)
    applied = raw(.typeapply, [], named(3))
    in_module = raw(.field, [], named(6)); nodes[in_module].name = 7
    plain_args = [plain, wrapped, fn_name, fn_local, mut_local, jo_local, hole, applied]
    xe_module_result = sym_of(.fns, 0)
    check_args_untyped([in_module])
    xe_module_result = 0
    check_args_untyped(plain_args)
    show_all("plain", plain_args + [lit, in_module])
    # Calls: members asked while unnamed, then by name; set literals by their members.
    call = raw(.call, [named(2)], named(11))
    check_args_untyped([call])
    members = raw(.call, [], named(5))
    other_call = raw(.call, [], named(12))
    set_item = named(2)
    set_lit = raw(.call, [set_item], named(9))
    check_args_untyped([members, other_call, set_lit])
    show_all("calls", [call, members, other_call, set_lit, set_item])
    # Records, maps, arrays (spread ones become records on the host).
    rec_item = named(3)
    record = raw(.record_lit, [rec_item])
    key = named(2)
    value = named(3)
    pair = raw(.pair, [], key); nodes[pair].b = i32(value)
    map = raw(.map_lit, [pair])
    empty_map = raw(.map_lit)
    arr_item = named(2)
    arr = raw(.array, [arr_item])
    spread_item = named(2); nodes[spread_item].flags = 1024
    spread = raw(.array, [spread_item])
    typed_arr = raw(.array, [named(2)]); nodes[typed_arr].type = i32(T_INT); nodes[typed_arr].flags = 128
    check_args_untyped([record, map, empty_map, arr, spread, typed_arr])
    show_all("literals", [record, rec_item, map, key, value, empty_map, arr, arr_item, spread, spread_item, typed_arr])
    # values_settled: an operator's own function; checked, waiting and one-value arguments;
    # spreads, packs, marked hits, callable or unknown names and unchecked calls go to the host
    xe_module_result = 0
    g = intern_text("g")
    checked = raw(.int_lit); nodes[checked].flags = 128
    hit = raw(.int_lit); nodes[hit].flags = 128
    loop cz_marks.len() <= hit: cz_marks.push(false)
    cz_marks[hit] = true
    spread_arg = named(2); nodes[spread_arg].flags = 1024
    values_tuple = raw(.tuple); nodes[values_tuple].aux = 7
    fn_arg = raw(.namedarg, [], named(4))
    settled_args = [[checked], [named(2)], [named(4)], [named(3)], [named(20)], [spread_arg], [values_tuple], [hit], [raw(.lambda)], [fn_arg], [raw(.call, [], named(g))], [raw(.call, [], named(5))], [checked, named(2), raw(.hole)], []]
    loop args in settled_args: print("settled:{args.len()}:{values_settled(raw(.call, args, named(g)))}")
    loop text in ["__op", "$", "$f", "_f"]: print("settled:{text}:{values_settled(raw(.call, [named(4)], named(intern_text(text))))}")
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_args_twins(compiler, tmp_path, release):  # noqa: F811
    from tests.test_selfhost_checker_resolve import compare
    assert compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS, jo_doubles=JO_DOUBLES).endswith(b'ok\n')
