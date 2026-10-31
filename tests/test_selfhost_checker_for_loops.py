"""For loops: ranges, elements, places, dictionaries and value loops match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_loops import DRIVER as LOOPS
from tests.selfhost_expr_double import compare_leaf

STEMS = ('checker_loops', 'checker_for_loops')
DRIVER = LOOPS + r'''
locals: Local[] = [Local()]
value_loops: ValueLoop[]
fl_rewritten = false
fl_entries_ok = true
fl_route_ok = true
fl_view_type = 0
fl_grow_once = false
fl_rewrite_host = (s: int) -> bool:
    events.push("rewrite:{s}")
    fl_rewritten
fl_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if fl_grow_once:
        fl_grow_once = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); locals.push(Local()); structs.push(StructInfo())
    last = n
    int(nodes[n].type)
fl_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    n
fl_literal_host = (n: int) -> int:
    events.push("literal:{n}")
    T_INT
fl_binding_host = (name: int, t: int, pos: int) -> int:
    events.push("binding:{name}:{t}")
    locals.push(Local(name = i32(name), type = i32(t)))
    scopes.names.push(name)
    locals.len() - 1
fl_open_host = (s: int): events.push("open:{s}")
fl_view_host = (s: int, t: int) -> int:
    events.push("view:{s}:{t}")
    if fl_view_type != 0: return fl_view_type
    t
fl_entries_host = (t: int) -> bool:
    events.push("entries:{t}")
    fl_entries_ok
fl_collide_host = (s: int): events.push("collide:{s}")
fl_element_host = (s: int, name: int, t: int, idx: int, fixed: bool) -> int:
    events.push("element:{s}:{name}:{t}:{idx}:{fixed}")
    locals.push(Local(name = i32(name), type = i32(t), flags = 8))
    locals.len() - 1
fl_route_host = (n: int) -> bool:
    events.push("route:{n}")
    fl_route_ok
fl_fields_host = (si: int): events.push("fields:{si}")
fl_map_value_host = (s: int, name: int, t: int, idx: int) -> int:
    events.push("map-value:{s}:{name}:{t}:{idx}")
    locals.push(Local(name = i32(name), flags = 8))
    locals.len() - 1
fl_map_ref_host = (l: int): events.push("map-ref:{l}")
fl_body_host = (b: int): events.push("body:{b}:{ctxs[cx].loop_depth}:{labels.len()}:{serials}:{value_loops.len()}")
fl_reset_host = (mark: int):
    events.push("reset:{mark}")
    scopes.names.truncate(mark)
fl_error_host = (n: int, t: int, code: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
fl_services = CheckerForHost(fl_rewrite_host, fl_coerce_host, fl_literal_host, fl_binding_host, fl_open_host, fl_view_host, fl_entries_host, fl_collide_host, fl_element_host, fl_route_host, fl_fields_host, fl_map_value_host, fl_map_ref_host, fl_body_host, fl_reset_host, fl_error_host)
fl_inputs = CheckerForInput(&nodes, &lists, &types, &structs, &fields, &files, &locals, &scopes, &serials, &serial_next, &value_loops, &cx, &last, &T_INT, &T_U8, &fl_services)
fl_bound = checker_for_loops_bind(&fl_inputs)
DEWY = 1 << 40
named_var = (name: int) -> int:
    v = node(.ident); nodes[v].name = i32(name); v
for_of = (it: int, names: int[], dewy: bool = true, flags: int = 0, ival: int = 0, label: int = 0) -> int:
    vars: int[]
    loop nm in names: vars.push(named_var(nm))
    s = node(.for_, it, ival, 0, vars)
    nodes[s].b = i32(node(.block))
    nodes[s].flags = i32(flags)
    nodes[s].sval = i32(label)
    if dewy: nodes[s].pos = DEWY + s
    s
lit = (t: int) -> int:
    n = typed(.int_lit, t); nodes[n].flags = i32(256); n
span = (a: int, b: int, c: int = 0) -> int:
    r = node(.range, a); nodes[r].b = i32(b); nodes[r].c = i32(c)
    if c != 0: nodes[r].flags = i32(32768)
    r
named_struct = (name: str, field_types: int[]) -> int:
    first = fields.len()
    loop ft in field_types: fields.push(Field(type = i32(ft)))
    structs.push(StructInfo(name = name, fields = i32(first), nfields = i32(field_types.len())))
    types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    types.len() - 1
run = (s: int):
    fl_for(s)
    print("{s}:{nodes[s].a}:{nodes[s].sym}:{nodes[s].aux}:{nodes[s].c}:{nodes[s].d}:{nodes[s].aux2}:{ctxs[cx].loop_depth}:{serials}:{value_loops.len()}:{scopes.names.len()}")
    if nodes[s].sym > 0: print("  {locals[int(nodes[s].sym)].flags}")
prepare_for = ():
    prepare_loops()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_for()
    # Ranges: endpoints joined to the written one, literal defaults, steps, open ends.
    run(for_of(span(lit(T_INT), typed(.ident, T_I32)), [11]))
    run(for_of(span(lit(T_INT), lit(T_INT)), [11]))
    run(for_of(span(lit(T_INT), lit(T_INT), typed(.ident, T_U8)), [11]))
    run(for_of(span(lit(T_INT), lit(T_INT), lit(T_INT)), [11]))
    run(for_of(span(typed(.ident, T_I16), 0), [11]))
    run(for_of(span(typed(.ident, T_I16), 0), [11], false))
    # Rewritten sources stop here.
    fl_rewritten = true
    run(for_of(span(lit(T_INT), lit(T_INT)), [11]))
    fl_rewritten = false
    # Elements by value (Dewy value loops), counted, in place, of text and fixed arrays.
    arr = int(tb_mk_array(T_STR))
    fl_grow_once = true
    run(for_of(typed(.ident, arr), [12]))
    fl_route_ok = false
    run(for_of(typed(.ident, arr), [12]))
    fl_route_ok = true
    run(for_of(typed(.ident, arr), [12], false))
    run(for_of(typed(.ident, arr), [13, 12], true, 0, 1))
    run(for_of(typed(.ident, arr), [12], true, 1))
    run(for_of(typed(.ident, T_STR), [12]))
    fixed = int(tb_mk_fixed(T_INT, 4))
    run(for_of(typed(.ident, fixed), [12], true, 1))
    run(for_of(typed(.ident, fixed), [12]))
    types.push(TypeInfo(kind = .range)); rv = types.len() - 1
    run(for_of(typed(.ident, rv), [12]))
    # Dictionaries and their entries; views the host makes; labels.
    map = named_struct("Map", [int(tb_mk_array(T_STR)), int(tb_mk_array(T_INT))])
    run(for_of(typed(.ident, map), [14]))
    run(for_of(typed(.ident, map), [14, 15]))
    run(for_of(typed(.ident, map), [14, 15], true, 1))
    entries = named_struct("__MapEntries", [int(tb_mk_array(T_U8)), int(tb_mk_array(T_U16))])
    run(for_of(typed(.ident, entries), [14, 15]))
    fl_view_type = arr
    run(for_of(typed(.ident, map), [12], true, 0, 1))
    fl_view_type = 0
    run(for_of(typed(.ident, arr), [12], true, 0, 0, 9))
    loop l in labels: print("{l.context}:{l.name}:{l.depth}")
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_for_loops_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare_leaf(compiler, tmp_path, release, DRIVER + MAIN, 'fl_check_host', extra_stems=STEMS).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(for_of(span(0, lit(T_INT)), [11]))', 1),
    ('run(for_of(span(typed(.ident, T_STR), lit(T_INT)), [11]))', 2),
    ('run(for_of(span(typed(.ident, T_FLOAT), lit(T_INT)), [11]))', 3),
    ('run(for_of(span(typed(.float_lit, T_INT), lit(T_INT)), [11]))', 3),
    ('run(for_of(span(lit(T_INT), lit(T_INT)), [11, 12]))', 4),
    ('run(for_of(span(lit(T_INT), lit(T_INT)), [11], true, 1))', 5),
    ('run(for_of(typed(.ident, T_STR), [12], true, 1))', 6),
    ('run(for_of(typed(.ident, named_struct("Map", [T_INT, T_INT])), [12], true, 1))', 7),
    ('run(for_of(typed(.ident, T_INT), [12]))', 8),
    ('fl_entries_ok = false; run(for_of(typed(.ident, named_struct("__MapEntries", [T_INT, T_INT])), [12]))', 8),
])
def test_checker_for_loops_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_for()
    {case}
    print("unreachable")
'''
    output = compare_leaf(compiler, tmp_path, False, DRIVER + main, 'fl_check_host', status=19, extra_stems=STEMS)
    assert output.rstrip().endswith(f':{code}'.encode())
