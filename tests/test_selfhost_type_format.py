"""Type spellings retain bytes, callback ordering and the recursive display budget."""
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
main = ():
    reset()
    fields = [Field(name=2, type=1), Field(name=3, type=2)]
    params = [4, 0]
    types[23].id = 0
    types[10].st = 1
    math_id = add(TypeInfo(kind=.int_, bits=64, sign=true, rep=.tagged_int))
    mat_id = add(TypeInfo(kind=.vec, bits=16))
    kinds: TK[] = [.void_, .float_, .ptr, .box, .null_, .range, .none_lit, .vec, .cfn, .fixed, .polyfn, .dimension]
    loop kind in kinds:
        add(TypeInfo(kind=kind, bits=32, sign=true, elem=1, args=2, nargs=2))
    add(TypeInfo(kind=.void_, flags=8))
    add(TypeInfo(kind=.int_, bits=32, sign=false, st=1))
    add(TypeInfo(kind=.int_, bits=8, sign=true, st=2))
    add(TypeInfo(kind=.tuple, args=2, nargs=2, sign=true))
    add(TypeInfo(kind=.fn_, elem=i32(types.len() - 1), sign=true))
    add(TypeInfo(kind=.fn_, elem=7, sign=true))
    add(TypeInfo(kind=.param, id=4))
    add(TypeInfo(kind=.param, id=7))
    loop policy in [100, 101, 102]: add(TypeInfo(kind=.refined, elem=1, st=i32(policy)))
    map = record("Map", [1, 2])
    add(TypeInfo(kind=.refined, elem=i32(map), bits=-1))
    record("Set", [1], 93)
    record("Set", [1], 0)
    record("Rational", [], 91)
    record("Rational", [], 0)
    record("RationalWord", [], 92)
    record("NDArray", [2])
    record("Anonymous", [], 0, false, true)
    record("Literal", [], 0, false, false, 1)
    record("SoA", [1], 0, false, false, 0, true)
    base_error = record("BaseError", [])
    child_error = record("ChildError", [])
    parents[child_error] = base_error
    record("Errors", [base_error, child_error, 2], 0, true)
    start = args.len()
    loop i in [0..70): args.push(1)
    add(TypeInfo(kind=.fn_, elem=0, args=i32(start), nargs=70, mutmask=1))
    current = 1
    loop i in [0..12):
        start = args.len()
        args.push(i32(current)); args.push(i32(current))
        current = add(TypeInfo(kind=.tuple, args=i32(start), nargs=2))
    count = types.len()
    saved_types = types
    saved_structs = structs
    saved_fields = fields
    saved_args = args
    type_format_bind(&format_input)
    loop dewy in [false, true]:
        loop t in [0..count):
            print("{t}:{tf_string(t, dewy)}")
            print("post:{tf_postfix(t, dewy)}")
    assert(format_grew and saved_types.len() == count and saved_fields.len() == 2)
    assert(saved_structs.len() < structs.len() and saved_args.len() < args.len())
    a = tf_string(current, true)
    b = tf_string(current, true)
    assert(a == b and contains(a, "…"), "bounded recursive spelling resets its budget")
    print(a)
    print("ok")

'''

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_format_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_format')
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
