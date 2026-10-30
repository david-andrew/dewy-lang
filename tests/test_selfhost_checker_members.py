"""Member selection: receivers, spellings, modules, tuples, vectors and record fields match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xd_sentinel_name = 0
xd_ide_on = false
xd_len_id = 41
xd_ptr_id = 42
xd_narrows = 0
xd_no_narrow = 0
xd_set = false
xd_copy = -1
xd_typeval_bypass = false
xd_vector_bypass = false
xd_method = 0
xd_fn = -1
xd_missing_bypass = false
xd_grow = false
xd_receiver_host = (n: int, expected: int) -> int:
    events.push("receiver:{n}:{expected}")
    if xd_grow:
        xd_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); structs.push(StructInfo()); fields.push(Field())
    int(nodes[int(nodes[n].a)].type)
xd_secret_host = (n: int, t: int) -> int:
    events.push("secret:{n}:{t}")
    T_BOOL
xd_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    n
xd_set_host = (t: int) -> bool:
    events.push("set:{t}")
    xd_set
xd_map_host = (t: int) -> bool:
    events.push("map:{t}")
    false
xd_copy_host = (n: int, t: int) -> int:
    events.push("copy:{n}:{t}")
    xd_copy
xd_forward_host = (n: int, t: int, expected: int) -> int:
    events.push("forward:{n}:{t}:{expected}")
    T_STR
xd_complete_host = (t: int): events.push("complete:{t}")
xd_len_host = (n: int, t: int): events.push("len:{n}:{t}")
xd_call_host = (n: int, data: bool, expected: int) -> int:
    events.push("call:{n}:{data}:{expected}")
    T_INT
xd_module_host = (n: int, t: int, expected: int, callee: bool) -> int:
    events.push("module:{n}:{t}:{expected}:{callee}")
    T_FLOAT
xd_type_host = (n: int, t: int, expected: int, callee: bool, bypass: mut bool) -> int:
    events.push("type:{n}:{t}:{expected}:{callee}")
    bypass = xd_typeval_bypass
    T_U8
xd_vector_host = (n: int, t: int, expected: int, bypass: mut bool) -> int:
    events.push("vector:{n}:{t}:{expected}")
    bypass = xd_vector_bypass
    T_F32
xd_deref_host = (pos: int, t: int): events.push("deref:{pos}:{t}")
xd_fields_host = (si: int):
    events.push("fields:{si}")
    structs[si].resolved = true
xd_field_ref_host = (n: int, si: int, fi: int, t: int): events.push("field-ref:{n}:{si}:{fi}:{t}")
xd_method_host = (t: int) -> int:
    events.push("method:{t}")
    xd_method
xd_method_value_host = (n: int, m: int, callee: bool, expected: int) -> int:
    events.push("method-value:{n}:{m}:{callee}:{expected}")
    T_I8
xd_fn_host = (n: int, t: int, callee: bool, expected: int) -> int:
    events.push("fn:{n}:{t}:{callee}:{expected}")
    xd_fn
xd_narrow_host = (n: int, t: int) -> int:
    events.push("narrow:{n}:{t}")
    T_I16
xd_missing_host = (n: int, t: int, expected: int, bypass: mut bool) -> int:
    events.push("missing:{n}:{t}:{expected}")
    bypass = xd_missing_bypass
    T_I32
xd_error_host = (n: int, code: int, t: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
xd_services = CheckerMemberHost(xd_receiver_host, xd_secret_host, xd_coerce_host, xd_set_host, xd_map_host, xd_copy_host, xd_forward_host, xd_complete_host, xd_len_host, xd_call_host, xd_module_host, xd_type_host, xd_vector_host, xd_deref_host, xd_fields_host, xd_field_ref_host, xd_method_host, xd_method_value_host, xd_fn_host, xd_narrow_host, xd_missing_host, xd_error_host)
xd_inputs = CheckerMemberInput(&nodes, &types, &structs, &fields, &args, &files, &xd_sentinel_name, &xd_ide_on, &xd_len_id, &xd_ptr_id, &xd_narrows, &xd_no_narrow, &T_STR, &xd_services)
xd_binding = checker_members_bind(&xd_inputs)
DEWY = 1 << 40
member = (t: int, name: int, dewy: bool = true) -> int:
    r = node(.ident); nodes[r].type = i32(t)
    n = node(.field, r); nodes[n].name = i32(name)
    if dewy: nodes[n].pos = DEWY + n
    n
record_of = (names: int[], ftypes: int[], resolved: bool = true) -> int:
    first = fields.len()
    loop i in [0..names.len()): fields.push(Field(name = i32(names[i]), type = i32(ftypes[i])))
    structs.push(StructInfo(fields = i32(first), nfields = i32(names.len()), resolved = resolved))
    types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    types.len() - 1
kind_of = (k: TK) -> int:
    types.push(TypeInfo(kind = k)); types.len() - 1
run = (n: int, expected: int = 0, spelled: int = 0, callee: bool = false):
    r = xd_member(n, expected, spelled, callee)
    print("{n}:{r.type}:{r.bypass}:{nodes[n].aux}")
prepare_members = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_members()
    poly = kind_of(.polyfn)
    fn_t = int(tb_mk_fn([T_INT], T_INT, 0, 0, 0, false))
    rec = record_of([5, 6, 5, 7, 8], [T_INT, T_STR, T_BOOL, poly, fn_t], false)
    xd_grow = true
    run(member(rec, 5))
    run(member(rec, 6, false))
    xd_ide_on = true
    run(member(rec, 6))
    xd_ide_on = false
    # Methods and function-valued fields; narrowed paths.
    xd_method = 77
    run(member(rec, 7))
    run(member(rec, 7), 0, 0, true)
    xd_method = 0
    run(member(rec, 7))
    xd_fn = T_U16
    run(member(rec, 8))
    xd_fn = -1
    run(member(rec, 8))
    xd_narrows = 1
    run(member(rec, 6))
    narrowed = member(rec, 6); xd_no_narrow = narrowed
    run(narrowed)
    xd_narrows = 0
    run(member(int(tb_mk_ptr(rec)), 6))
    # Missing members, secrets, string sets, copies, unions and optionals.
    run(member(rec, 9))
    xd_missing_bypass = true
    run(member(rec, 9))
    xd_missing_bypass = false
    run(member(kind_of(.secret), 5))
    structs.push(StructInfo(lit_set = 2)); types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1)))
    run(member(types.len() - 1, 5))
    xd_copy = T_U64
    run(member(rec, 4), 0, 4)
    xd_copy = -1
    run(member(rec, 4), 0, 4)
    run(member(int(tb_mk_opt(rec)), 5))
    run(member(int(tb_mk_opt(rec)), 5, false))
    xd_sentinel_name = 5
    run(member(rec, 5))
    xd_sentinel_name = 0
    # Spellings: len, length, ptr; modules, type members, tuple positions, vectors.
    arr = int(tb_mk_array(T_INT))
    run(member(arr, 41))
    run(member(arr, 2), 0, 2)
    run(member(arr, 2, false), 0, 2)
    run(member(rec, 2), 0, 2)
    run(member(arr, 42))
    run(member(arr, 42, false))
    run(member(kind_of(.module), 5), T_INT, 0, true)
    tv = kind_of(.typeval)
    run(member(tv, 5))
    xd_typeval_bypass = true
    run(member(tv, 5))
    pair = int(tb_mk_tuple([T_INT, T_STR]))
    p = member(pair, 0); nodes[p].aux = -2; nodes[p].ival = 1
    run(p)
    run(member(T_VEC3, 5))
    xd_vector_bypass = true
    run(member(T_VEC3, 5))
    run(member(T_INT, 5))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_members_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_members',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('xd_set = true; run(member(T_INT, 3), 0, 1)', 1),
    ('p = member(T_INT, 0); nodes[p].aux = -2; run(p)', 2),
    ('p = member(int(tb_mk_tuple([T_INT])), 0); nodes[p].aux = -2; nodes[p].ival = 1; run(p)', 3),
    ('p = member(int(tb_mk_tuple([T_INT])), 0); nodes[p].aux = -2; nodes[p].ival = -1; run(p)', 3),
])
def test_checker_members_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_members()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_members',))
    assert output.rstrip().endswith(f':{code}'.encode())
