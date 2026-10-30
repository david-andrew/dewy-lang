"""`is?` tests: rewrite selection and direct union/optional tests match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xi_seen = 0
xi_family = false
xi_members = -1
xi_value = -1
xi_implies = false
xi_replacement = 0
xi_grow = false
xi_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xi_grow:
        xi_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); structs.push(StructInfo())
    xi_seen = n
    if xi_replacement != 0:
        xi_seen = xi_replacement; xi_replacement = 0
    int(nodes[xi_seen].type)
xi_finalize_host = (n: int) -> int:
    events.push("finalize:{n}")
    int(nodes[n].type)
xi_original_host = (n: int) -> int:
    events.push("original:{n}")
    if nodes[n].kind == .ident: return 900 + n
    0
xi_family_host = (t: int) -> bool:
    events.push("family:{t}")
    xi_family
xi_family_test_host = (n: int, orig: int, at: int, tt: int) -> int:
    events.push("family-test:{n}:{orig}:{at}:{tt}")
    T_FLOAT
xi_members_host = (n: int, orig: int, u: int, tt: int, optional: bool) -> int:
    events.push("members:{n}:{orig}:{u}:{tt}:{optional}")
    xi_members
xi_set_host = (n: int, orig: int, at: int, set: int) -> int:
    events.push("set:{n}:{orig}:{at}:{set}")
    T_STR
xi_value_host = (n: int, orig: int, at: int, tt: int, set: int) -> int:
    events.push("value:{n}:{orig}:{at}:{tt}:{set}")
    xi_value
xi_refined_host = (n: int, orig: int, tt: int) -> int:
    events.push("refined:{n}:{orig}:{tt}")
    T_INT
xi_implies_host = (a: int, b: int) -> bool:
    events.push("implies:{a}:{b}")
    xi_implies
xi_presence_host = (n: int) -> int:
    events.push("presence:{n}")
    44
xi_error_host = (n: int, at: int, tt: int, code: int):
    print(events)
    print("error:{n}:{at}:{tt}:{code}")
    exit(19)
xi_services = CheckerTypeTestHost(xi_check_host, xi_finalize_host, xi_original_host, xi_family_host, xi_family_test_host, xi_members_host, xi_set_host, xi_value_host, xi_refined_host, xi_implies_host, xi_presence_host, xi_error_host)
xi_inputs = CheckerTypeTestInput(&nodes, &types, &structs, &refine, &xi_seen, &T_STR, &T_BOOL, &xi_services)
xi_binding = checker_type_tests_bind(&xi_inputs)
record_type = () -> int:
    structs.push(StructInfo(resolved = true))
    types.push(TypeInfo(kind = .struct_, st = i32(structs.len() - 1)))
    types.len() - 1
union_type = (members: int[]) -> int:
    first = args.len()
    loop m in members: args.push(i32(m))
    structs.push(StructInfo(targs = i32(first), ntargs = i32(members.len()), union_ = true, resolved = true))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1)))
    types.len() - 1
set_type = (set: int) -> int:
    structs.push(StructInfo(lit_set = i32(set), resolved = true))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1)))
    types.len() - 1
operand = (t: int, k: NK = .ident) -> int:
    n = node(k); nodes[n].type = i32(t); n
is_test = (at: int, tt: int, k: NK = .ident) -> int:
    n = node(.istype, operand(at, k)); nodes[n].b = i32(node(.tname, 0, tt, 3)); n
run = (n: int):
    t = xi_check(n)
    print("{n}:{t}:{nodes[n].a}:{nodes[n].aux}:{nodes[n].aux2}:{xi_seen}")
prepare_tests = () -> int[]:
    prepare()
    refine = false
    a = record_type(); b = record_type(); c = record_type()
    r = int(types.len()); types.push(TypeInfo(kind = .refined, elem = i32(T_INT)))
    [a, b, c, union_type([a, b, c]), union_type([a, b]), union_type([a, T_INT]), set_type(2), set_type(3), r]
'''

MAIN = r'''
main = ():
    m = prepare_tests()
    a = m[0]; b = m[1]; c = m[2]; u = m[3]; v = m[4]; w = m[5]; s = m[6]; s2 = m[7]; r = m[8]
    opt_u = int(tb_mk_opt(u)); opt_a = int(tb_mk_opt(a))
    # Family annotations: only unions and optionals ask, and a plain type skip.
    xi_grow = true
    run(is_test(a, u))
    xi_family = true
    run(is_test(a, u, .field))
    skipped = is_test(a, u); nodes[int(nodes[skipped].b)].aux = -7
    xi_family = false
    run(is_test(u, a))
    run(skipped)
    # Optional unions and union subsets ask for their member tests.
    xi_members = T_FLOAT
    run(is_test(opt_u, v))
    run(is_test(u, v))
    xi_members = -1
    # String sets compare text or another set's words; refinements compare values.
    run(is_test(T_STR, s))
    run(is_test(s2, s))
    xi_value = T_BOOL
    run(is_test(w, r))
    xi_value = -1
    run(is_test(T_INT, r))
    # Direct tests: a union member, optional presence, and already narrowed values.
    replacement = operand(u); xi_replacement = replacement
    run(is_test(T_INT, c))
    run(is_test(u, a))
    run(is_test(opt_a, T_NONE))
    run(is_test(opt_a, a))
    refine = true
    xi_implies = true
    run(is_test(opt_a, b))
    refine = false
    run(is_test(a, a))
    run(is_test(a, v))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_type_tests_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_type_tests',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(is_test(m[3], record_type()))', 1),
    ('run(is_test(m[5], m[8]))', 1),
    ('run(is_test(int(tb_mk_opt(m[0])), m[1]))', 2),
    ('refine = true; run(is_test(int(tb_mk_opt(m[0])), m[1]))', 2),
    ('run(is_test(m[0], m[1]))', 3),
])
def test_checker_type_tests_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    m = prepare_tests()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_type_tests',))
    assert output.rstrip().endswith(f':{code}'.encode())
