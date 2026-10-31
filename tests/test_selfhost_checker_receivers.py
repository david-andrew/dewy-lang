"""Field and index receiver preludes: products, reflection, private fields, soa aliases, spellings,
bracket calls, `end`, sets, stored ranges, stepped slices and text match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_indexes import DRIVER as INDEXES
from tests.test_selfhost_checker_literals import DRIVER as LITERALS
from tests.test_selfhost_checker_members import DRIVER as MEMBERS
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

STEMS = ('checker_exact', 'checker_literals', 'checker_members', 'checker_indexes', 'checker_receivers')
BASE = RESOLVER.split('main = ():')[0]
DRIVER = (MEMBERS + LITERALS.split('main = ():')[0][len(BASE):]
          + INDEXES.split('main = ():')[0][len(BASE):].split('DEWY = 1 << 40')[0] + r'''
rv_ide_on = false
rv_reflecting = false
rv_reflect_hit = false
rv_callee_at = 0
rv_soa_count = 0
rv_soa_hit = -1
rv_last = 0
rv_private_rewrite = false
rv_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    nodes.push(nodes[n])
    rv_last = nodes.len() - 1
    int(nodes[n].type)
rv_juxt_host = (n: int): events.push("juxt:{n}")
rv_reflect_name_host = (n: int):
    events.push("reflect-name:{n}")
    nodes[n].b = 0
rv_reflect_member_host = (n: int) -> bool:
    events.push("reflect-member:{n}")
    if rv_reflect_hit: nodes[n].type = i32(T_U32)
    rv_reflect_hit
rv_private_host = (n: int) -> int:
    events.push("private:{n}")
    a = int(nodes[n].a)
    if rv_private_rewrite:
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); structs.push(StructInfo())
        nodes.push(nodes[a])
        a = nodes.len() - 1
        nodes[n].a = i32(a)
    a
rv_soa_alias_host = (n: int, a0: int, expected: int) -> int:
    events.push("soa-alias:{n}:{a0}:{expected}")
    rv_soa_hit
rv_soa_index_host = (n: int, a0: int, expected: int) -> int:
    events.push("soa-index:{n}:{a0}:{expected}")
    T_U8
rv_bracket = false
rv_set = false
rv_index_base = 0
rv_type_receiver = 5
rv_empty = 0
rv_bracket_host = (n: int) -> bool:
    events.push("bracket:{n}")
    rv_bracket
rv_end_host = (n: int, expected: int) -> int:
    events.push("end:{n}:{expected}")
    T_U16
rv_set_host = (t: int) -> bool:
    events.push("set-type:{t}")
    rv_set
rv_ranges_host = (n: int, t: int): events.push("ranges:{n}:{t}")
rv_stepped_host = (n: int, t: int, expected: int) -> int:
    events.push("stepped:{n}:{t}:{expected}")
    T_U32
rv_text_host = (n: int, expected: int) -> int:
    events.push("text:{n}:{expected}")
    T_STR
rv_error_host = (n: int, t: int, code: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
rv_services = CheckerReceiverHost(rv_check_host, rv_juxt_host, rv_reflect_name_host, rv_reflect_member_host, rv_private_host, rv_soa_alias_host, rv_soa_index_host, rv_bracket_host, rv_end_host, rv_set_host, rv_ranges_host, rv_stepped_host, rv_text_host, rv_error_host)
rv_inputs = CheckerReceiverInput(&nodes, &types, &structs, &names, &files, &rv_ide_on, &rv_reflecting, &rv_callee_at, &rv_soa_count, &rv_last, &rv_index_base, &rv_type_receiver, &rv_empty, &rv_services)
rv_binding = checker_receivers_bind(&rv_inputs)
field_run = (n: int, expected: int = 0):
    t = xs_field(n, expected)
    print("{n}:{t}:{nodes[n].a}:{nodes[n].aux}:{nodes[n].type}")
named = (t: int, text: str, dewy: bool = true) -> int: member(t, intern_text(text), dewy)
item = (t: int, k: NK = .ident) -> int:
    n = node(k); nodes[n].type = i32(t); n
index_run = (n: int, expected: int = 0):
    t = xs_index(n, expected)
    print("{n}:{t}:{nodes[n].a}:{nodes[n].aux}:{nodes[n].type}:{rv_index_base}:{rv_type_receiver}:{rv_empty}")
indexed = (t: int, b: int, dewy: bool = true, extra: int[] = []) -> int:
    n = node(.index, item(t), 0, 0, extra); nodes[n].b = i32(b)
    if dewy: nodes[n].pos = DEWY + n
    n
named_record = (name: str) -> int:
    structs.push(StructInfo(name = name, resolved = true))
    types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    types.len() - 1
prepare_receivers = ():
    prepare_members()
    loop names.len() < 50: names.push("n{names.len()}")
''')

MAIN = r'''
main = ():
    prepare_receivers()
    rec = record_of([5, 6, intern_text("__peer"), intern_text("copy")], [T_INT, T_STR, T_BOOL, T_I8])
    field_run(member(rec, 5))
    field_run(member(rec, 6), T_STR)
    # Products, computed names, reflected members, callees.
    p = member(rec, 5); nodes[p].flags = i32(536870912); field_run(p)
    p = member(rec, 5); nodes[p].b = i32(node(.str_lit)); field_run(p)
    rv_reflecting = true
    field_run(member(rec, 6))
    rv_reflect_hit = true
    field_run(member(rec, 6))
    rv_reflecting = false
    rv_reflect_hit = false
    p = member(rec, 5); rv_callee_at = p; field_run(p)
    # A library's own fields: asked for outside the editor and loop counters.
    field_run(named(rec, "__peer"))
    rv_private_rewrite = true
    field_run(named(rec, "__peer"))
    rv_private_rewrite = false
    rv_ide_on = true
    field_run(named(rec, "__peer"))
    rv_ide_on = false
    p = named(rec, "__peer"); nodes[p].flags = i32(33554432); field_run(p)
    # Soa element aliases are asked about only once one exists, and only for names.
    field_run(member(rec, 5))
    rv_soa_count = 1
    field_run(member(rec, 5))
    rv_soa_hit = T_I16
    field_run(member(rec, 5))
    rv_soa_hit = -1
    # ps[i].x: the indexed receiver is checked; a soa array's is rewritten.
    ix = node(.index, node(.ident)); nodes[ix].b = i32(node(.int_lit))
    nodes[int(nodes[ix].a)].type = i32(int(tb_mk_array(rec)))
    p = node(.field, ix); nodes[p].name = 5; nodes[p].pos = DEWY + p
    field_run(p)
    structs.push(StructInfo(soa_ = true)); types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    ix = node(.index, node(.ident)); nodes[ix].b = i32(node(.int_lit))
    nodes[int(nodes[ix].a)].type = i32(types.len() - 1)
    p = node(.field, ix); nodes[p].name = 5
    field_run(p)
    ix = node(.index, node(.ident))
    p = node(.field, ix); nodes[p].name = 5
    field_run(p)
    # Spellings: add, length, copy.
    arr = int(tb_mk_array(T_INT))
    field_run(named(arr, "length"))
    field_run(named(arr, "add"))
    xd_copy = T_U64
    field_run(named(rec, "copy"))
    xd_copy = -1
    field_run(named(rec, "copy"))
    # Indexes: plain, products, Dewy bracket calls, `end`, empty brackets.
    arr = int(tb_mk_array(T_STR))
    index_run(indexed(arr, item(T_INT, .int_lit), false))
    index_run(indexed(arr, item(T_INT, .int_lit)), T_STR)
    p = indexed(arr, item(T_INT, .int_lit)); nodes[p].flags = i32(536870912); index_run(p)
    index_run(indexed(rec, 0, true, [item(T_INT, .int_lit)]))
    rv_bracket = true
    index_run(indexed(rec, 0, true, [item(T_INT, .int_lit)]))
    index_run(indexed(rec, 0, false, [item(T_INT, .int_lit)]))
    rv_bracket = false
    p = indexed(arr, item(T_INT, .ident)); nodes[p].sval = 7; index_run(p)
    index_run(indexed(kind_of(.typeval), 0))
    # Sets the host does not confirm; stored ranges; n-dimensional arrays; steps; text.
    index_run(indexed(named_record("Set"), item(T_INT, .int_lit)))
    two = [item(T_INT, .int_lit), item(T_INT, .int_lit)]
    index_run(indexed(rec, 0, true, two))
    index_run(indexed(rec, 0, false, two))
    index_run(indexed(named_record("NDArray"), 0, true, two))
    index_run(indexed(kind_of(.typeval), item(T_INT, .int_lit)))
    step = node(.range, item(T_INT, .int_lit)); nodes[step].flags = i32(32768)
    index_run(indexed(arr, step))
    step = node(.range, item(T_INT, .int_lit)); nodes[step].flags = i32(32768)
    xx_part = T_I32
    index_run(indexed(named_record("NDArray"), step))
    xx_part = -1
    index_run(indexed(T_STR, item(T_INT, .int_lit)))
    index_run(indexed(T_STR, item(T_INT, .int_lit), false))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_receivers_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('xd_set = true; field_run(named(T_INT, "add"))', 1),
    ('p = member(T_INT, 0); nodes[p].aux = -2; field_run(p)', 2),
    ('rv_set = true; index_run(indexed(named_record("Set"), item(T_INT, .int_lit)))', 1),
])
def test_checker_receivers_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_receivers()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS)
    assert output.rstrip().endswith(f':{code}'.encode())
