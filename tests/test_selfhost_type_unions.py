"""Canonical unions preserve inference identity, callback order and arena snapshots."""
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
variants: Variant[]
sets: str[][]
never = 0
none_type = 0
strings: {str: int} = {}
render_grew = false
literal = (values: str[]) -> int:
    loop si in [1..structs.len()):
        set = int(structs[si].lit_set)
        if set != 0 and sets[set] == values: return int(structs[si].type)
    set = sets.len()
    sets.push(values)
    id = types.len()
    si = structs.len()
    structs.push(StructInfo(type=i32(id), lit_set=i32(set)))
    types.push(TypeInfo(kind=.enum_, st=i32(si)))
    id
literal_of = (t0: int) -> int:
    t = tu_prune(t0)
    if types[t].kind != .enum_: return 0
    int(structs[int(types[t].st)].lit_set)
optional = (e: int) -> int:
    t = TypeInfo(kind=.opt, elem=i32(e))
    type_intern(&t, [])
text = (t: int) -> str:
    events.push("text:{t}")
    if not render_grew:
        render_grew = true
        grow()
        loop i in [0..128):
            fields.push(Field())
            variants.push(Variant())
        assert(uu_mk_union([1]) == 1, "reentrant canonical member")
    "t{t}"
name_id = (s: str) -> int:
    if let id = strings.get(s): return id
    id = strings.len() + 1
    strings[s] = id
    id
union_host = TypeUnionHost(optional, literal_of, literal, text, text, name_id)
union_input = TypeUnionInput(&types, &structs, &args, &fields, &variants, &sets, &never, &none_type, &union_host)
union_reset = ():
    reset()
    fields = []
    variants = []
    sets = [[]]
    strings = {}
    render_grew = false
    none_type = types.len()
    types.push(TypeInfo(kind=.none_lit))
    never = types.len()
    types.push(TypeInfo(kind=.void_, flags=8))
    type_union_bind(&union_input)
main = ():
    loop round in [0..2):
        union_reset()
        assert(uu_mk_union([]) == none_type and uu_mk_union([never]) == none_type)
        assert(uu_mk_union([1, 1, never]) == 1)
        old_types = types
        old_structs = structs
        old_args = args
        xs = [2, 1, 2, never]
        saved = xs
        u: int = int(uu_mk_union(xs))
        assert(xs == saved and render_grew)
        assert(uu_mk_union([1, 2]) == u and uu_mk_union([u, 1, u]) == u, "canonical concrete union")
        assert(tu_union_members(u) == [1, 2])
        o: int = int(uu_mk_union([none_type, u]))
        assert(types[o].kind == .opt and int(types[o].elem) == u)
        assert(uu_mk_union([o, none_type, 1]) == o, "nested optional flattening")
        v: int = int(uu_mk_union([4, 2]))
        assert(uu_mk_union([2, 4]) == v, "unresolved structural candidate")
        assert(tu_unify(4, 1))
        assert(uu_mk_union([v, 1]) == u, "resolved inference union flattens")
        a = literal(["alpha"])
        b = literal(["beta", "alpha"])
        lit: int = int(uu_mk_union([a, b]))
        assert(sets[literal_of(lit)] == ["alpha", "beta"], "literal sets join in first-seen order")
        mixed: int = int(uu_mk_union([a, 3, b]))
        print(tu_union_members(mixed))
        assert(old_types.len() == 27 and old_structs.len() == 5 and old_args.len() == 15, "retained arena snapshots")
        assert(old_types[4].ref == 0)
        render()
        loop s in structs: print("struct:{s.type}:{s.fields}:{s.nfields}:{s.variants}:{s.nvariants}:{s.targs}:{s.ntargs}:{s.name}:{s.lit_set}")
        loop f in fields: print("field:{f.name}:{f.type}:{f.offset}:{f.boxed}")
        loop v in variants: print("variant:{v.name}:{v.fields}:{v.nfields}:{v.tag}:{v.value}")
        print(sets)
    print("ok")

'''

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_union_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_unions')
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
