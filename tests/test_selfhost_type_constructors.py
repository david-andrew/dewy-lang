"""Builtin IDs, constructors and recursive secret erasure match their frozen owner."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
types: TypeInfo[] = [TypeInfo()]
args: i32[]
table: i32[]
structs: StructInfo[]
binds = 0
unused_one = (a: int) -> int: 0
unused_two = (a: int, b: int) -> int: 0
unused_three = (a: int, b: int, c: int) -> int: 0
unused_four = (a: int, b: int, c: int, d: int) -> int: 0
unused_subst = (a: int, values: int[], zonking: bool) -> int: 0
unused_inst = (a: int, values: int[]) -> int: 0
unused_make = (t: TypeInfo, values: int[]) -> int: 0
unused_union = (values: int[]) -> int: 0
inference_host = TypeInferenceHost(unused_three, unused_subst, unused_one, unused_two, unused_subst, unused_four, unused_inst, unused_make, unused_union)
inference_input = TypeInferenceInput(&types, &structs, &args, &binds, &inference_host)
inference_binding = type_inference_bind(&inference_input)
intern_binding = type_intern_bind(&types, &args, &table)
events: str[]
reenter = false
ptr_size = 8
var_counter = 0
secrets_seen = false
values_any = false
T_VOID = 0
T_BOOL = 0
T_INT = 0
T_MATH_INT = 0
T_I8 = 0
T_I16 = 0
T_I32 = 0
T_U8 = 0
T_U16 = 0
T_U32 = 0
T_U64 = 0
T_FLOAT = 0
T_F32 = 0
T_STR = 0
T_NULL = 0
T_RANGE = 0
T_NONE = 0
T_NEVER = 0
T_RAWPTR = 0
T_VEC2 = 0
T_VEC3 = 0
T_VEC4 = 0
T_MAT4 = 0
T_IVEC2 = 0
T_IVEC3 = 0
T_IVEC4 = 0

make = (t: TypeInfo, values: int[]) -> int:
    events.push("{int(t.kind)}:{t.elem}:{t.bits}:{t.flags}:{t.id}:{t.size}:{t.align}:{values}")
    if reenter:
        reenter = false
        tb_mk_var()
    type_intern(&t, values)
host = TypeConstructorHost(make)
input = TypeConstructorInput(&types, &ptr_size, &var_counter, &secrets_seen, &values_any, &T_VOID, &T_BOOL, &T_INT, &T_MATH_INT, &T_I8, &T_I16, &T_I32, &T_U8, &T_U16, &T_U32, &T_U64, &T_FLOAT, &T_F32, &T_STR, &T_NULL, &T_RANGE, &T_NONE, &T_NEVER, &T_RAWPTR, &T_VEC2, &T_VEC3, &T_VEC4, &T_MAT4, &T_IVEC2, &T_IVEC3, &T_IVEC4, &host)
binding = type_constructor_bind(&input)
main = ():
    loop word in [8, 4]:
        types = [TypeInfo()]
        args = []; table = []; structs = []
        binds = 0; var_counter = 0; secrets_seen = false; values_any = false
        events = []
        ptr_size = word
        tb_init_types()
        assert(T_VOID == 1 and T_BOOL == 2 and T_INT == 3 and T_MATH_INT == 4, "builtin allocation order")
        assert(types[T_STR].size == i32(word) and types[T_NULL].align == i32(word))
        assert(types[T_MATH_INT].rep == .tagged_int and types[T_NEVER].flags == 10)
        assert(types[T_VEC3].size == 12 and types[T_VEC3].align == 4 and types[T_IVEC4].sign)
        saved_types = types
        saved_args = args
        saved_table = table
        nt = types.len(); na = args.len()
        array: int = int(tb_mk_array(T_INT))
        assert(tb_mk_array(T_INT) == array)
        secret: int = int(tb_mk_secret(T_INT))
        assert(secrets_seen and tb_mk_secret(secret) == secret)
        wrapped: int = int(tb_mk_array(secret))
        assert(tb_secret_repr(wrapped) == array)
        ptr: int = int(tb_mk_ptr(secret))
        opt: int = int(tb_mk_opt(ptr))
        fixed: int = int(tb_mk_fixed(opt, 3))
        box: int = int(tb_mk_box(fixed))
        plain: int = int(tb_secret_repr(box))
        assert(types[plain].kind == .box)
        p = int(types[plain].elem)
        assert(types[p].kind == .fixed and types[p].bits == 3)
        p = int(types[p].elem)
        assert(types[p].kind == .opt)
        p = int(types[p].elem)
        assert(types[p].kind == .ptr and types[int(types[p].elem)].kind == .int_)
        first: int = int(tb_mk_var()); second: int = int(tb_mk_var())
        assert(first != second and types[first].id == 1 and types[second].id == 2 and var_counter == 2)
        param: int = int(tb_mk_param(7))
        assert(tb_mk_param(7) == param)
        reenter = true
        fn: int = int(tb_mk_fn([T_INT, T_STR], T_BOOL, 3, 99, 88, true))
        assert(not reenter and var_counter == 3)
        assert(tb_mk_fn([T_INT, T_STR], T_BOOL, 3, 99, 88, true) == fn)
        assert(types[fn].kind == .fn_ and types[fn].st == 99 and types[fn].bits == 88 and types[fn].sign)
        print(tb_mk_cfn([T_INT], T_BOOL))
        # The implementation-language fields truncate to signed 32-bit words.
        assert(tb_mk_fixed(T_INT, 4294967299) == tb_mk_fixed(T_INT, 3))
        assert(tb_mk_param(4294967303) == param)
        wide = int(tb_mk_fn([T_INT], T_BOOL, 4294967299, 4294967395, 4294967384, true))
        assert(types[wide].mutmask == 3 and types[wide].st == 99 and types[wide].bits == 88)
        low = int(tb_mk_fixed(T_INT, -9223372036854775807 - 1))
        assert(types[low].bits == 0)
        fresh = int(tb_mk_var())
        assert(types[fresh].args == i32(args.len()) and types[fresh].nargs == 0 and types[fresh].flags == 1)
        tuple: int = int(tb_mk_tuple([T_INT, T_STR], false))
        values: int = int(tb_mk_values([T_INT, T_STR]))
        assert(tuple != values and values_any and types[values].sign)
        a: int = int(tb_mk_typeval(T_INT)); b: int = int(tb_mk_typeval(T_INT))
        assert(a != b and types[a].flags == 2 and types[a].kind == .typeval)
        a = int(tb_mk_modval(123)); b = int(tb_mk_modval(123))
        assert(a != b and types[a].mod == 123 and types[a].kind == .module)
        assert(saved_types.len() == nt and saved_args.len() == na and saved_table != table, "constructor arena snapshots")
        loop t in types: print("{int(t.kind)}:{t.elem}:{t.bits}:{t.flags}:{t.id}:{t.size}:{t.align}:{t.args}:{t.nargs}:{t.st}:{t.mod}:{int(t.rep)}:{t.sign}:{t.mutmask}")
        print(args)
        print(table)
        print(events)
    print("ok")

'''

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_constructor_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_constructors')
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
