"""Type interning requests, inference queries and layouts agree with frozen Jo."""

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401


SERVICES = '''use 'checker_types.dewy'
const TF_HAS_VAR = 1
types: TypeInfo[]
structs: StructInfo[]
type_args: i32[]
layout_calls = 0

layout = (t: int):
    layout_calls += 1

type_query_equal_shape = (ts: mut TypeInfo[], ss: mut StructInfo[], args: mut i32[], a: int, b: int) -> bool:
    ts[a].kind == ts[b].kind and ts[a].elem == ts[b].elem

type_intern = (t: *TypeInfo, args: int[]) -> int:
    assert(t[0].kind == .fn_ and t[0].sign and t[0].elem == 2)
    assert(args == [1, 4])
    int(t[0].bits)
'''

DRIVER = '''main = ():
    types = [TypeInfo(), TypeInfo(kind=.int_), TypeInfo(kind=.float_, size=8), TypeInfo(kind=.var, ref=2, flags=1), TypeInfo(kind=.vec), TypeInfo(kind=.fn_, sign=true, elem=2), TypeInfo(kind=.array, elem=3, flags=1, args=1), TypeInfo(kind=.array, elem=3, flags=1), TypeInfo(kind=.enum_, st=1)]
    structs = [StructInfo(), StructInfo(union_=true, targs=1, ntargs=2)]
    type_args = [7, 1, 4]
    assert(type_access_targ(6, 1) == 4 and type_access_struct_targ(1, 0) == 1)
    assert(type_access_prune(3) == 2 and type_access_prune(0) == 0)
    assert(type_access_tkind(3) == .float_ and type_access_telem(5) == 2)
    assert(type_access_has_var(3) and not type_access_has_var(2) and type_access_fn_type_pack(5))
    assert(type_access_is_int(1) and not type_access_is_int(3) and type_access_is_float(3))
    assert(type_access_is_numeric(1) and type_access_is_numeric(3) and not type_access_is_numeric(4))
    assert(type_access_is_vec(4) and not type_access_is_vec(5))
    assert(type_access_type_eq(2, 3) and type_access_type_eq(6, 7))
    assert(not type_access_type_eq(0, 5) and not type_access_type_eq(2, 4))
    assert(type_access_align_up(17, 8) == 24 and type_access_align_up(-7, 8) == 0)
    assert(type_access_tsize(3) == 8 and type_access_talign(3) == 1 and layout_calls == 2)
    assert(type_access_is_union(8) and not type_access_is_union(1))
    assert(type_access_union_members(8) == [1, 4])
    assert(type_access_mk_type(TypeInfo(kind=.fn_, sign=true, elem=2, bits=91), [1, 4]) == 91)
    assert(type_access_mk_type(TypeInfo(kind=.fn_, sign=true, elem=2, bits=6), [1, 4]) == 6)
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_access_twins(compiler, tmp_path, release):
    assert compare_narrow(compiler, tmp_path, release, ('checker_types', 'type_access'), DRIVER,
                          doubles={'services.jo': SERVICES},
                          services=('type_intern', 'type_ops', 'type_queries', 'types')) == b'ok\n'
