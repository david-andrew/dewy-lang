"""Recursive type-property walks retain completed-root caching and COW semantics."""
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
refine_active = false
ptr_size = 8
property_grew = false
property_events: str[]
property_resolve = (si: int):
    property_events.push("resolve:{si}")
    if property_grew: return
    property_grew = true
    loop i in [0..128):
        types.push(TypeInfo())
        structs.push(StructInfo())
        fields.push(Field())
        variants.push(Variant())
        args.push(0)
    assert(not tp_type_has_fn(1), "reentrant completed primitive query")
texture = (si: int) -> bool: structs[si].decl == 42
layout_box = (t: int) -> int:
    v = TypeInfo(kind=.box, elem=i32(t))
    type_intern(&v, [])
property_base = (t: int) -> int: int(tp_base(t))
property_optional = (t: int) -> bool: tp_math_optional(t)
endless = (si: int, f: int, vi: int): property_events.push("endless:{si}:{f}:{vi}")
cycle = (si: int): property_events.push("cycle:{si}")
padded = (t: int) -> bool: false
layout_host = TypeLayoutHost(property_resolve, layout_box, property_base, property_optional, endless, cycle, padded)
layout_input = TypeLayoutInput(&types, &structs, &args, &fields, &variants, &ptr_size, &layout_host)
property_host = TypePropertyHost(texture, property_resolve)
property_input = TypePropertyInput(&types, &structs, &args, &fields, &variants, &refine_active, &math_id, &property_host)
main = ():
    reset()
    fields = []
    variants = []
    params = []
    types[1].size = 8; types[1].align = 8; types[1].flags = 2
    types[2].size = 8; types[2].align = 8; types[2].flags = 6
    types[3].size = 1; types[3].align = 1; types[3].flags = 2
    type_format_bind(&format_input)
    type_layout_bind(&layout_input)
    type_property_bind(&property_input)
    # A -> B -> A is a back edge, while another edge from A reaches a closure.
    # B must not inherit a provisional negative answer from that first search.
    a = record("A", [])
    b = record("B", [])
    d = record("D", [])
    sa = int(types[a].st); sb = int(types[b].st); sd = int(types[d].st)
    fields = [Field(type=10, name=2), Field(type=i32(b), name=3), Field(type=i32(a), name=2), Field(type=i32(d), name=2)]
    structs[sa].fields = 0; structs[sa].nfields = 2
    structs[sb].fields = 2; structs[sb].nfields = 1
    structs[sd].fields = 3; structs[sd].nfields = 1
    old_types = types; old_structs = structs; old_fields = fields
    assert(tp_type_has_fn(a) and tp_type_has_fn(b), "cache only completed graph roots")
    assert(not tp_type_has_fn(d), "cycle without a closure terminates")
    assert(property_grew and old_fields.len() == 4 and old_structs.len() < structs.len())
    count = property_events.len()
    assert(tp_type_has_fn(a) and not tp_type_has_fn(d))
    assert(property_events.len() == count, "completed roots are memoized")
    math_id = add(TypeInfo(kind=.int_, rep=.tagged_int, size=8, align=8, flags=2))
    opt_math = add(TypeInfo(kind=.opt, elem=i32(math_id)))
    arr = add(TypeInfo(kind=.array, elem=1))
    refined_arr = add(TypeInfo(kind=.refined, elem=i32(arr)))
    quantity_arr = add(TypeInfo(kind=.quantity, elem=i32(arr)))
    secret_arr = add(TypeInfo(kind=.secret, elem=i32(arr)))
    fixed = add(TypeInfo(kind=.fixed, elem=1, bits=3))
    texture_type = record("Texture", [], 42)
    structs[int(types[texture_type].st)].nfields = 0
    value = record("Plain", [])
    structs[int(types[value].st)].fields = i32(fields.len())
    structs[int(types[value].st)].nfields = 1
    fields.push(Field(type=1, name=2))
    en = record("Enum", [], 0, true)
    structs[int(types[en].st)].nfields = 0
    enum_si = int(types[en].st)
    structs[enum_si].nvariants = 2
    structs[enum_si].variants = 0
    variants = [Variant(), Variant()]
    nominal_enum = record("Nominal", [])
    types[nominal_enum].kind = .enum_
    ns = int(types[nominal_enum].st)
    structs[ns].nfields = 0; structs[ns].nvariants = 2; structs[ns].variants = 0
    assert(tp_is_managed(math_id) and not tp_is_aggregate(opt_math) and tp_math_optional(opt_math))
    assert(not tp_simple_enum(en) and tp_simple_enum(nominal_enum))
    assert(tp_plain_problem(texture_type) == "Texture" and tp_plain_problem(value) == "")
    loop active in [false, true]:
        refine_active = active
        assert(tp_is_managed(refined_arr) == active and tp_is_aggregate(refined_arr) == false)
        assert(tp_is_managed(quantity_arr) and tp_is_managed(secret_arr))
        loop t in [1, 2, 3, 10, a, b, d, math_id, opt_math, arr, refined_arr, quantity_arr, secret_arr, fixed, texture_type, value, en, nominal_enum]:
            print("{active}:{t}:{tp_is_managed(t)}:{tp_is_aggregate(t)}:{tp_type_has_fn(t)}:{tp_plain_problem(t)}")
    assert(not old_fields[0].boxed and old_types[a].flags == 0, "layout preserves snapshots")
    print(property_events)
    type_property_bind(&property_input)
    assert(tp_type_has_fn(b), "rebinding clears only the query memo")
    print("ok")

'''

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_property_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_format', 'type_layout', 'type_properties')
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
