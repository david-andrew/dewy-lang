"""Bare variants: optional and union enum selection and lazy fields match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xv_sentinel_name = 0
xv_ide_on = false
xv_grow = false
xv_fields_host = (si: int):
    events.push("fields:{si}")
    structs[si].resolved = true
    if xv_grow:
        xv_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); structs.push(StructInfo()); args.push(0); variants.push(Variant())
xv_complete_host = (t: int): events.push("complete:{t}")
xv_reference_host = (n: int, t: int, vi: int): events.push("reference:{n}:{t}:{vi}")
xv_error_host = (n: int, t: int, code: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
xv_services = CheckerVariantHost(xv_fields_host, xv_complete_host, xv_reference_host, xv_error_host)
xv_inputs = CheckerVariantInput(&nodes, &types, &structs, &args, &variants, &xv_sentinel_name, &xv_ide_on, &xv_services)
xv_binding = checker_variants_bind(&xv_inputs)
enum_type = (names: int[], fielded: int, resolved: bool) -> int:
    first = variants.len()
    loop name in names: variants.push(Variant(name = i32(name), nfields = i32(if name == fielded: 1 else: 0)))
    structs.push(StructInfo(variants = i32(first), nvariants = i32(names.len()), resolved = resolved))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1)))
    types.len() - 1
union_type = (members: int[]) -> int:
    first = args.len()
    loop m in members: args.push(i32(m))
    structs.push(StructInfo(targs = i32(first), ntargs = i32(members.len()), union_ = true, resolved = true))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1)))
    types.len() - 1
dot = (name: int) -> int:
    n = node(.dotname); nodes[n].name = i32(name); n
run = (name: int, ex: int):
    n = dot(name)
    t = xv_check(n, ex)
    print("{name}:{ex}:{t}:{nodes[n].aux}")
prepare_variants = () -> int[]:
    prepare()
    a = enum_type([1, 2, 3], 3, false)
    b = enum_type([2, 4], 0, true)
    [a, b, union_type([a, b, T_INT]), int(tb_mk_opt(a))]
'''

MAIN = r'''
main = ():
    made = prepare_variants()
    a = made[0]; b = made[1]; u = made[2]; opt = made[3]
    xv_grow = true
    run(4, u)
    run(1, a)
    run(2, a)
    run(2, opt)
    run(4, b)
    xv_sentinel_name = 2
    run(2, b)
    xv_ide_on = true
    run(1, a)
    run(4, u)
    alias = enum_type([7], 0, true)
    run(7, union_type([alias, T_STR]))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_variants_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_variants',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(1, 0)', 1),
    ('run(1, T_INT)', 1),
    ('run(2, made[2])', 2),
    ('run(9, made[0])', 2),
    ('run(3, made[0])', 3),
])
def test_checker_variants_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    made = prepare_variants()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_variants',))
    assert output.rstrip().endswith(f':{code}'.encode())
