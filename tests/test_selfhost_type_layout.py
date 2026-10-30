"""Recursive boxing, layout and finite defaults against the frozen owner."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
types: TypeInfo[]
structs: StructInfo[]
args: i32[]
fields: Field[]
variants: Variant[]
pointer_size = 8
events: str[]
grew = false
resolve = (si: int):
    events.push("resolve:{si}")
    if grew: return
    grew = true
    loop i in [0..128):
        types.push(TypeInfo())
        structs.push(StructInfo())
        args.push(0)
        fields.push(Field())
        variants.push(Variant())
    tl_layout(1)
box = (e: int) -> int:
    events.push("box:{e}")
    loop t in [0..types.len()):
        if types[t].kind == .box and int(types[t].elem) == e: return t
    types.push(TypeInfo(kind=.box, elem=i32(e)))
    types.len() - 1
base = (t0: int) -> int:
    t = tl_prune(t0)
    if types[t].kind == .secret: t = tl_prune(int(types[t].elem))
    if types[t].kind == .callable: t = tl_prune(int(types[t].elem))
    if types[t].kind == .refined: t = tl_prune(int(types[t].elem))
    if types[t].kind == .quantity: return tl_prune(int(types[t].elem))
    t
math_opt = (t: int) -> bool: types[t].kind == .opt and base(int(types[t].elem)) == 23
endless = (si: int, f: int, vi: int): events.push("endless:{si}:{f}:{vi}")
cycle = (si: int): events.push("cycle:{si}")
padded = (t: int) -> bool: structs[int(types[t].st)].decl == 77
host = TypeLayoutHost(resolve, box, base, math_opt, endless, cycle, padded)
input = TypeLayoutInput(&types, &structs, &args, &fields, &variants, &pointer_size, &host)
reset = ():
    types = [TypeInfo(), TypeInfo(kind=.int_, bits=64, sign=true, size=8, align=8, flags=2), TypeInfo(kind=.bool_, size=1, align=1, flags=2), TypeInfo(kind=.str_, size=i32(pointer_size), align=i32(pointer_size), flags=6), TypeInfo(kind=.array, elem=1), TypeInfo(kind=.ptr, elem=1), TypeInfo(kind=.fn_, elem=1), TypeInfo(kind=.opt, elem=1), TypeInfo(kind=.fixed, elem=1, bits=3), TypeInfo(kind=.tuple, args=0, nargs=3), TypeInfo(kind=.struct_, st=1), TypeInfo(kind=.opt, elem=10), TypeInfo(kind=.struct_, st=2), TypeInfo(kind=.enum_, st=3), TypeInfo(kind=.enum_, st=4), TypeInfo(kind=.enum_, st=5), TypeInfo(kind=.struct_, st=6), TypeInfo(kind=.quantity, elem=1), TypeInfo(kind=.refined, elem=1), TypeInfo(kind=.callable, elem=6), TypeInfo(kind=.secret, elem=3), TypeInfo(kind=.box, elem=1), TypeInfo(kind=.opt, elem=23), TypeInfo(kind=.int_, size=8, align=8, flags=2, rep=.tagged_int), TypeInfo(kind=.fixed, elem=12, bits=0), TypeInfo(kind=.struct_, st=7)]
    structs = [StructInfo(), StructInfo(type=10, fields=0, nfields=1, name="Good"), StructInfo(type=12, fields=1, nfields=1, name="Bad"), StructInfo(type=13, variants=0, nvariants=2, name="Enum"), StructInfo(type=14, variants=2, nvariants=2), StructInfo(type=15, variants=4, nvariants=2, union_=true), StructInfo(type=16, fields=3, nfields=1, decl=77), StructInfo(type=25, fields=4, nfields=1, soa_=true)]
    args = [i32(2), i32(1), i32(3)]
    fields = [Field(type=11), Field(type=12), Field(type=13), Field(type=2), Field(type=4)]
    variants = [Variant(fields=2, nfields=1), Variant(), Variant(), Variant(), Variant(), Variant()]
    events = []
    grew = false
    type_layout_bind(&input)
main = ():
    loop word in [8, 4]:
        pointer_size = word
        reset()
        old_types = types
        old_structs = structs
        old_fields = fields
        old_variants = variants
        loop t in [0..26): tl_layout(t)
        assert(grew and old_types.len() == 26 and old_fields.len() == 5)
        assert(old_types[10].flags == 0 and not old_structs[1].boxes_done and not old_fields[0].boxed, "COW arena mutations")
        assert(old_variants[0].fields == 2)
        assert(fields[0].boxed and fields[1].boxed and fields[2].boxed)
        assert(tl_box_default(10) == -1 and tl_box_default(12) == -2 and tl_box_default(13) == 1, "finite default selection")
        assert(tl_zero_ends(24), "zero-length fixed recursive type ends")
        assert(types[16].size == 128 and types[16].align == 1, "cache padding preserves natural alignment")
        assert(structs[4].simple_enum and not structs[5].simple_enum, "nominal enum vs union")
        assert(types[22].size == 8, "tagged optional representation")
        loop a in [10, 11, 12, 13, 24, 25]:
            loop b in [10, 12, 13]: print("holds:{a}:{b}:{tl_type_holds(a, b)}")
        loop t in types: print("type:{int(t.kind)}:{t.elem}:{t.size}:{t.align}:{t.flags}")
        loop s in structs: print("struct:{s.payload_off}:{s.simple_enum}:{s.resolving}:{s.boxes_done}")
        loop f in fields: print("field:{f.type}:{f.offset}:{f.boxed}")
        print(events)
        reset()
        assert(tl_box_default(13) == 1 and tl_box_default(12) == -2, "rebind clears recursive memo state")
    print("ok")
'''

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_layout_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in ('checker_types', 'type_layout'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use 'checker_types.{extension}'\nuse 'type_layout.{extension}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
