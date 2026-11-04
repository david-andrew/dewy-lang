"""Member-call receiver context, dispatch and UFCS rewrites match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_call_expr import DRIVER as CALL
from tests.test_selfhost_checker_expr import JO_DOUBLES, STEMS
from tests.test_selfhost_checker_resolve import compare

DRIVER = CALL + r'''
use 'expr.jo'
kids = (n: int) -> int[]: node_kids(mut nodes, mut lists, n)
member_call = (rt: int, name: int = 4, xs: int[] = []) -> int:
    recv = done(rt)
    callee = node(.field, recv); nodes[callee].name = i32(name)
    node(.call, callee, 0, 0, xs)
member_show = (n: int, expected: int = 0):
    callee = int(nodes[n].a)
    result = call_member(n, expected)
    print("member:{result}:{type_receiver_at}:{nodes[callee].a}:{kids(n)}")
    print(events); events = []
'''
MAIN = r'''
main = ():
    prepare_expr()
    loop names.len() < 32: names.push("f{names.len()}")
    type_receiver_at = 77
    zn_early = int(T_INT)
    module = types.len(); types.push(TypeInfo(kind=.module, mod=6))
    typeval = types.len(); types.push(TypeInfo(kind=.typeval, elem=i32(T_BOOL)))
    record = types.len(); types.push(TypeInfo(kind=.struct_))
    pointer = types.len(); types.push(TypeInfo(kind=.ptr, elem=i32(record)))
    # Module dispatch keeps the written argument list and uses the module's family.
    member_show(member_call(module, 4, [done(T_INT)]), T_INT)
    member_show(member_call(typeval))
    # A service can coerce the receiver type before dispatch (e.g. a literal union).
    zm_receiver_type = module
    member_show(member_call(T_STR))
    zm_receiver_type = 0
    zm_prepared = int(T_FLOAT)
    member_show(member_call(record))
    zm_prepared = -1
    zm_soa = true
    member_show(member_call(T_INT))
    zm_soa = false
    zm_field = int(T_BOOL)
    member_show(member_call(record))
    member_show(member_call(pointer))
    zm_field = -1
    # A field miss falls through; a keyed method can finish in the tail.
    zm_tail = int(T_FLOAT)
    member_show(member_call(record))
    zm_tail = -1
    member_show(member_call(T_INT, 30))
    # Uniform syntax prepends the receiver after the tail's name/argument rewrites.
    zm_name = 9; zm_extra = done(T_BOOL); zm_grow = true
    n = member_call(T_INT, 4, [done(T_FLOAT)])
    recv = int(nodes[int(nodes[n].a)].a)
    member_show(n)
    assert(not zm_grow and kids(n)[0] == recv and kids(n)[2] == zm_extra)
    assert(int(nodes[recv].flags) & 128 != 0 and type_receiver_at == 77)
    zm_name = 0; zm_extra = 0
    # Juxtaposed products finish before receiver dispatch.
    n = member_call(T_INT)
    nodes[n].flags = 536870912; nodes[int(nodes[n].a)].flags = 536870912
    zc_numeric = true
    member_show(n)
    zc_numeric = false
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_member_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare(compiler, tmp_path, release, DRIVER + MAIN,
                     extra_stems=STEMS, jo_doubles=JO_DOUBLES)
    assert output.endswith(b'ok\n')
    for branch in (b'member-type:', b'member-soa:', b'member-field:', b'member-len:',
                   b'member-juxt:', b'member-product:', b'by-name:9:-1:'):
        assert branch in output


@pytest.mark.parametrize('type_value', [False, True], ids=['receiver', 'type-value'])
def test_checker_call_member_errors(compiler, tmp_path, type_value):  # noqa: F811
    main = '''main = ():
    prepare_expr()
    zm_error = true
    t = T_INT
'''
    if type_value:
        main += '    t = types.len(); types.push(TypeInfo(kind=.typeval, elem=i32(T_BOOL)))\n'
    main += '    call_member(member_call(t), 0)\n'
    compare(compiler, tmp_path, False, DRIVER + main, status=19,
            extra_stems=STEMS, jo_doubles=JO_DOUBLES)
