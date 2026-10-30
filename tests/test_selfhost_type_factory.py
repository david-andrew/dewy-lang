"""Canonical record/SOA instances and bounded nesting retain frozen behavior."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''


types: TypeInfo[]
structs: StructInfo[]
args: i32[]
table: i32[]
binds = 0
events: str[]
grew = false
ib = type_intern_bind(&types, &args, &table)

grow = ():
    if grew: return
    grew = true
    loop i in [0..128):
        types.push(TypeInfo())
        structs.push(StructInfo())
        args.push(0)
    assert(tu_zonk(1) == 1, "reentrant concrete zonk")
make = (t: TypeInfo, values: int[]) -> int:
    events.push("make:{int(t.kind)}:{t.elem}:{t.st}:{t.bits}:{values}")
    grow()
    type_intern(&t, values)
make_kind = (k: TK, elem: int, st: int, bits: int) -> int: make(TypeInfo(kind=k, elem=i32(elem), st=i32(st), bits=i32(bits)), [])
callable = (t: int, e: int, cap: int) -> int: make_kind(.callable, t, e, cap)
effect_subst = (e: int, values: int[], zonking: bool) -> int:
    events.push("effect:{e}:{values}:{zonking}")
    grow()
    e + 100
effect = (e: int) -> int: make_kind(.effect, 0, e, 0)
refined = (t: int, p: int) -> int: make_kind(.refined, t, p, 0)
ref_subst = (p: int, values: int[], zonking: bool) -> int:
    events.push("refine:{p}:{values}:{zonking}")
    grow()
    p + 200
quantity = (t: int, dim: int, pos: int, tag: int) -> int: make_kind(.quantity, t, dim, tag)
make_union = (input: int[]) -> int:
    events.push("union:{input}")
    grow()
    work = input
    members: int[]
    i = 0
    loop i < work.len():
        t = tu_prune(work[i])
        i += 1
        if tu_is_union(t):
            loop m in tu_union_members(t): work.push(m)
        else if not members.contains(t): members.push(t)
    members.sort()
    if members.len() == 1: return members[0]
    loop si in [1..structs.len()):
        if not structs[si].union_ or int(structs[si].ntargs) != members.len(): continue
        same = true
        loop j in [0..members.len()):
            if tu_struct_targ(si, j) != members[j]: same = false
        if same: return int(structs[si].type)
    start = args.len()
    flags = 0
    loop t in members:
        args.push(i32(t))
        if tu_has_var(t): flags = 1
    si = structs.len()
    id = types.len()
    structs.push(StructInfo(decl=-3, targs=i32(start), ntargs=i32(members.len()), type=i32(id), union_=true))
    types.push(TypeInfo(kind=.enum_, st=i32(si), flags=i32(flags)))
    id
make_struct = (decl: int, values: int[]) -> int:
    events.push("struct:{decl}:{values}")
    grow()
    if decl == -3: return make_union(values)
    loop si in [1..structs.len()):
        if structs[si].decl != i32(decl) or int(structs[si].ntargs) != values.len(): continue
        same = true
        loop j in [0..values.len()):
            if tu_struct_targ(si, j) != values[j]: same = false
        if same: return int(structs[si].type)
    start = args.len()
    flags = 0
    loop t in values:
        args.push(i32(t))
        if tu_has_var(t): flags = 1
    si = structs.len()
    id = types.len()
    structs.push(StructInfo(decl=i32(decl), targs=i32(start), ntargs=i32(values.len()), type=i32(id)))
    types.push(TypeInfo(kind=.struct_, st=i32(si), flags=i32(flags)))
    id
host = TypeInferenceHost(callable, effect_subst, effect, refined, ref_subst, quantity, make_struct, make, make_union)
input = TypeInferenceInput(&types, &structs, &args, &binds, &host)
binding = type_inference_bind(&input)
reset = ():
    types = [TypeInfo(), TypeInfo(kind=.int_, bits=64, sign=true), TypeInfo(kind=.str_), TypeInfo(kind=.bool_), TypeInfo(kind=.var, flags=1, id=1), TypeInfo(kind=.var, flags=1, id=2), TypeInfo(kind=.array, elem=4, flags=1), TypeInfo(kind=.array, elem=1), TypeInfo(kind=.tuple, args=0, nargs=2, flags=1), TypeInfo(kind=.tuple, args=2, nargs=2), TypeInfo(kind=.fn_, args=4, nargs=2, elem=4, flags=1, mutmask=1), TypeInfo(kind=.fn_, args=6, nargs=2, elem=1, mutmask=1), TypeInfo(kind=.struct_, st=1, flags=1), TypeInfo(kind=.struct_, st=2), TypeInfo(kind=.enum_, st=3, flags=1), TypeInfo(kind=.enum_, st=4), TypeInfo(kind=.callable, elem=4, st=5, bits=2, flags=1), TypeInfo(kind=.effect, st=7, flags=1), TypeInfo(kind=.refined, elem=4, st=9, flags=1), TypeInfo(kind=.quantity, elem=4, st=42, bits=6, flags=1), TypeInfo(kind=.secret, elem=4, flags=1), TypeInfo(kind=.typeval, elem=4, flags=1), TypeInfo(kind=.module, flags=1), TypeInfo(kind=.param, flags=1), TypeInfo(kind=.var, ref=4, flags=1)]
    args = [i32(4), i32(2), i32(1), i32(2), i32(4), i32(2), i32(1), i32(2), i32(4), i32(1), i32(4), i32(2), i32(1), i32(2), i32(3)]
    structs = [StructInfo(), StructInfo(decl=123, targs=8, ntargs=1, type=12), StructInfo(decl=123, targs=9, ntargs=1, type=13), StructInfo(decl=-3, targs=10, ntargs=2, type=14, union_=true), StructInfo(decl=-3, targs=12, ntargs=3, type=15, union_=true)]
    table = []
    binds = 0
    events = []
    grew = false
render = ():
    print("binds:{binds}")
    loop t in types: print("{int(t.kind)}:{t.elem}:{t.args}:{t.nargs}:{t.st}:{t.flags}:{t.ref}:{t.bits}:{t.mutmask}")
    print(args)
    print(events)

fields: Field[]
params: int[]
parents: {int: int} = {}
math_id = 0
word_id = 1
mat_id = 0
names = ["", "lhs\n\n右", "value", "métre", "NamedT"]
format_grew = false
intervals = (t: int) -> (bool, int[]):
    if types[t].st == 100: return (true, [1, 3, 7, 7])
    if types[t].st == 101: return (true, [-1000000000000000, 0])
    if types[t].st == 102: return (true, [])
    (false, [])
span = (lo: int, hi: int, limit: int) -> bool: lo >= -(1 << 40) and hi <= (1 << 40) and hi - lo <= limit
dimension = (dim: int) -> str: "m{dim}"
name_text = (id: int) -> str: names[id]
set_text = (id: int) -> str: "'alpha' | 'β'"
resolve = (si: int):
    if format_grew: return
    format_grew = true
    loop i in [0..128):
        types.push(TypeInfo())
        structs.push(StructInfo())
        fields.push(Field())
        args.push(0)
    assert(tf_string(1, true) == "int64", "reentrant formatting")
rational = (t: int) -> bool: structs[int(types[t].st)].decl == 91
word_rational = (t: int) -> bool: structs[int(types[t].st)].decl == 92
set_type = (t: int) -> bool: structs[int(types[t].st)].decl == 93
format_host = TypeFormatHost(intervals, span, dimension, name_text, set_text, resolve, rational, word_rational, set_type)
format_input = TypeFormatInput(&types, &structs, &args, &fields, &params, &parents, &math_id, &word_id, &mat_id, &format_host)
add = (t: TypeInfo) -> int:
    types.push(t)
    types.len() - 1
record = (name: str, values: int[], decl: int = 0, union_: bool = false, anonymous: bool = false, lit: int = 0, soa: bool = false) -> int:
    start = args.len()
    loop t in values: args.push(i32(t))
    si = structs.len()
    id = types.len()
    structs.push(StructInfo(type=i32(id), name=name, decl=i32(decl), targs=i32(start), ntargs=i32(values.len()), fields=0, nfields=2, union_=union_, record_=anonymous, lit_set=i32(lit), soa_=soa))
    types.push(TypeInfo(kind=if union_ or lit != 0: .enum_ else: .struct_, st=i32(si)))
    id

variants: Variant[]
sets: str[][] = [[]]
none_type = 0
never_type = 0
soa_decl = 99
factory_grew = false
decl_grew = false
factory_events: str[]
factory_optional = (e: int) -> int:
    t = TypeInfo(kind=.opt, elem=i32(e))
    type_intern(&t, [])
no_set = (t: int) -> int: 0
no_literal = (s: str[]) -> int: 0
union_text = (t: int) -> str: tf_string(t, false)
union_name = (s: str) -> int:
    loop i in [0..names.len()):
        if names[i] == s: return i
    names.push(s)
    names.len() - 1
union_host = TypeUnionHost(factory_optional, no_set, no_literal, union_text, union_text, union_name)
union_input = TypeUnionInput(&types, &structs, &args, &fields, &variants, &sets, &never_type, &none_type, &union_host)
factory_fields = (si: int):
    factory_events.push("fields:{si}")
    if factory_grew: return
    factory_grew = true
    loop i in [0..128):
        types.push(TypeInfo())
        structs.push(StructInfo())
        fields.push(Field())
        args.push(0)
    tc_struct_inst(88, [1])
factory_array = (t: int) -> int:
    factory_events.push("array:{t}")
    a = TypeInfo(kind=.array, elem=i32(t))
    type_intern(&a, [])
declaration = (decl: int) -> TypeDeclInfo:
    factory_events.push("decl:{decl}")
    if not decl_grew:
        decl_grew = true
        loop i in [0..128):
            types.push(TypeInfo())
            structs.push(StructInfo())
            fields.push(Field())
            args.push(0)
        tc_struct_inst(77, [])
    TypeDeclInfo("decl{decl}", decl == 5, decl == 6)
nesting_error = (decl: int): factory_events.push("nesting:{decl}")
factory_host = TypeFactoryHost(factory_fields, factory_array, declaration, nesting_error)
factory_input = TypeFactoryInput(&types, &structs, &args, &fields, &soa_decl, &factory_host)
main = ():
    reset()
    fields = [Field(name=2, type=1), Field(name=3, type=2)]
    params = []
    type_format_bind(&format_input)
    type_union_bind(&union_input)
    type_factory_bind(&factory_input)
    old_types = types
    old_structs = structs
    old_fields = fields
    old_args = args
    simple: int = int(tc_struct_inst(10, []))
    assert(tc_struct_inst(10, []) == simple, "zero-argument structural group")
    generic: int = int(tc_struct_inst(10, [1, 2]))
    assert(tc_struct_inst(10, [1, 2]) == generic, "canonical concrete instance")
    variable: int = int(tc_struct_inst(10, [4]))
    assert(tc_struct_inst(10, [4]) == variable)
    assert(tu_unify(4, 1))
    assert(tc_struct_inst(10, [4]) == variable, "stored inference ID stays noncanonical")
    concrete: int = int(tc_struct_inst(10, [1]))
    assert(concrete != variable and types[concrete].flags == 0 and types[variable].flags == 1)
    assert(tc_struct_inst(10, [1]) == concrete)
    rec: int = int(tc_struct_inst(5, [1]))
    en: int = int(tc_struct_inst(6, [1]))
    assert(structs[int(types[rec].st)].record_ and types[en].kind == .enum_)
    assert(old_types.len() == 25 and old_structs.len() == 5 and old_fields.len() == 2 and old_args.len() == 15)
    assert(old_types[4].ref == 0 and decl_grew)
    point = record("Point", [], 10)
    soa: int = int(tc_struct_inst(soa_decl, [point]))
    assert(tc_soa_inst(point) == soa and factory_grew)
    si = int(types[soa].st)
    assert(structs[si].soa_ and structs[si].nfields == 2)
    loop i in [0..2): assert(types[int(fields[int(structs[si].fields) + i].type)].kind == .array)
    generic_soa: int = int(tc_soa_inst(23))
    assert(structs[int(types[generic_soa].st)].nfields == 0 and types[generic_soa].flags == 1)
    assert(tc_struct_inst(0, [1]) == 1, "union delegation")
    current = 1
    loop i in [0..51):
        current = add(TypeInfo(kind=.array, elem=i32(current)))
        loop limit in [0, 1, 2, 8, 48, 49, 100]: print("depth:{i}:{limit}:{tc_nesting(current, limit)}")
    tc_struct_inst(123, [current])
    assert(factory_events.contains("nesting:123"), "bounded expansion reports its declaration")
    before = factory_events.len()
    tc_struct_inst(123, [current])
    assert(factory_events.len() == before, "canonical hits do not repeat validation")
    render()
    print(factory_events)
    loop s in structs: print("struct:{s.type}:{s.decl}:{s.name}:{s.fields}:{s.nfields}:{s.targs}:{s.ntargs}:{s.soa_}:{s.record_}")
    loop f in fields: print("field:{f.name}:{f.type}")
    type_factory_bind(&factory_input)
    after: int = int(tc_struct_inst(10, [1]))
    assert(after != concrete, "rebinding starts fresh instance indexes")
    print("ok")

'''

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_factory_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_format', 'type_unions', 'type_factory')
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
