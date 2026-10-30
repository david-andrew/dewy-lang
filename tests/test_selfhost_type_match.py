"""Generic matching preserves costs, mutable bindings and recursive union capture."""
import subprocess
import pytest
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_type_constructors import DRIVER as CONSTRUCTOR_DRIVER

DRIVER = CONSTRUCTOR_DRIVER.split('main = ():')[0] + r'''
active = false
dewy = false
allow_source = 0
allow_dest = 0
grow_match = false
coercible = (n: int, source: int, dest: int) -> bool:
    assert(n == 0)
    if grow_match:
        grow_match = false
        loop i in [0..160]: types.push(TypeInfo()); args.push(0); structs.push(StructInfo())
        empty: int[]
        assert(tm_match(T_INT, T_INT, empty, 0) == 0)
    source == allow_source and dest == allow_dest
is_dewy = () -> bool: dewy
match_effect = (source: int, dest: int, values: mut int[]) -> bool:
    events.push("effects:{source}:{dest}")
    if source != 5 or dest != 9: return false
    values[1] = T_STR
    loop i in [0..160]: types.push(TypeInfo()); args.push(0)
    true
match_host = TypeMatchHost(coercible, is_dewy, match_effect)
match_binding = type_match_bind(&inference_input, &active, &T_NEVER, &T_MATH_INT, &match_host)
union_of = (values: int[]) -> int:
    if values.len() == 0: return T_NEVER
    if values.len() == 1: return values[0]
    first = args.len()
    loop value in values: args.push(i32(value))
    si = structs.len(); structs.push(StructInfo(union_=true, targs=i32(first), ntargs=i32(values.len())))
    hv = 0
    loop value in values:
        if tu_has_var(value): hv = 1
    types.push(TypeInfo(kind=.enum_, st=i32(si), flags=i32(hv)))
    types.len() - 1
record = (kind: TK, decl: int, values: int[]) -> int:
    first = args.len()
    loop value in values: args.push(i32(value))
    si = structs.len(); structs.push(StructInfo(decl=i32(decl), targs=i32(first), ntargs=i32(values.len())))
    types.push(TypeInfo(kind=kind, st=i32(si), flags=1))
    types.len() - 1
main = ():
    inference_host.mk_union = union_of
    loop word in [8, 4]:
        types = [TypeInfo()]; args = []; table = []; structs = []
        binds = 0; var_counter = 0; secrets_seen = false; values_any = false
        events = []; ptr_size = word; active = false; dewy = false
        allow_source = 0; allow_dest = 0
        tb_init_types()
        p = int(tb_mk_param(0)); q = int(tb_mk_param(1))
        values = [0, 0]; snapshot = values
        assert(tm_match(p, T_INT, values, 0) == 3 and values[0] == T_INT and snapshot[0] == 0)
        assert(tm_match(p, T_INT, values, 0) == 0)
        assert(tm_match(p, T_NEVER, values, 0) == 0)
        assert(tm_match(p, T_STR, values, 0) == -1)
        allow_source = T_STR; allow_dest = T_INT
        grow_match = true
        assert(tm_match(p, T_STR, values, 0) == 1 and not grow_match)
        values = [0, 0]
        ref = TypeInfo(kind=.refined, elem=i32(T_INT), st=11)
        types.push(ref); refined = types.len() - 1
        active = true
        assert(tm_match(p, refined, values, 1) == 0 and values[0] == refined)
        values = [0, 0]
        assert(tm_match(p, refined, values, 0) == 3 and values[0] == T_INT)
        active = false
        arr = int(tb_mk_array(p)); concrete = int(tb_mk_array(T_INT))
        values = [0, 0]
        assert(tm_match(arr, concrete, values, 0) == 0 and values[0] == T_INT)
        values = [0, 0]
        fixed = int(tb_mk_fixed(T_INT, 3))
        assert(tm_match(arr, fixed, values, 0) == 2 and values[0] == T_INT)
        values = [0, 0]
        assert(tm_match(tb_mk_opt(p), T_STR, values, 0) == 4 and values[0] == T_STR)
        assert(tm_match(tb_mk_fixed(p, 4), fixed, values, 0) == -1)
        values = [0, 0]
        pat = int(tb_mk_fn([p], q, 0)); actual = int(tb_mk_fn([T_INT], T_STR, 0))
        assert(tm_match(pat, actual, values, 0) == 0 and values == [T_INT, T_STR])
        values = [0, 0]
        assert(tm_match(tb_mk_cfn([p], q), tb_mk_cfn([T_INT], T_STR), values, 0) == 0)
        assert(tm_match(tb_mk_tuple([p, q], false), tb_mk_tuple([T_INT], false), values, 0) == -1)
        values = [0, 0]
        cp = TypeInfo(kind=.callable, elem=i32(p), st=9, flags=1)
        ca = TypeInfo(kind=.callable, elem=i32(T_INT), st=5)
        types.push(cp); call_pat = types.len() - 1
        types.push(ca); call_arg = types.len() - 1
        assert(tm_match(call_pat, call_arg, values, 0) == 3 and values == [T_INT, T_STR])
        loop kind in [TK.struct_, TK.enum_]:
            pat = record(kind, 7, [p, q]); actual = record(kind, 7, [T_INT, T_STR])
            values = [0, 0]
            assert(tm_match(pat, actual, values, 0) == 0 and values == [T_INT, T_STR])
            assert(tm_match(pat, record(kind, 8, [T_INT, T_STR]), values, 0) == -1)
        pat = union_of([p, T_BOOL]); actual = union_of([T_STR, T_INT, T_BOOL])
        values = [0, 0]
        assert(tm_match(pat, actual, values, 0) == 0)
        assert(tu_union_members(values[0]) == [T_STR, T_INT])
        values = [0, 0]
        assert(tm_match(pat, T_STR, values, 0) == 1 and values[0] == T_STR)
        assert(tm_param_in_union(tb_mk_array(pat), 0) and not tm_param_in_union(pat, 1))
        assert(not tm_param_in_union(T_INT, 0))
        allow_source = T_INT; allow_dest = T_MATH_INT
        assert(tm_match(T_MATH_INT, T_INT, values, 0) == 2)
        allow_source = T_F32; allow_dest = T_FLOAT
        assert(tm_match(T_FLOAT, T_F32, values, 0) == 4)
        allow_source = T_FLOAT; allow_dest = T_F32
        assert(tm_match(T_F32, T_FLOAT, values, 0) == 5)
        allow_source = 0; allow_dest = 0; dewy = true
        assert(tm_match(T_I8, T_INT, values, 0) == 20)
        dewy = false
        assert(tm_match(T_I8, T_INT, values, 0) == -1)
        print(values); print(events)
    print("ok")
'''
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_match_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_constructors', 'type_match')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
