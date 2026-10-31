"""Resource-type predicates (ownership_types) match their frozen Jo twin."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_type_properties import DRIVER as PROPERTIES

STEMS = ('checker_types', 'checker_tokens', 'checker_state', 'refinement_types', 'refine_predicates',
         'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_format', 'type_layout',
         'type_properties', 'type_constructors', 'ownership_types')

DRIVER = PROPERTIES.split('main = ():')[0] + r'''
fns: FnInst[] = [FnInst()]
decls: {int: int} = {}
copies: {int: int} = {}
moves: {int: int} = {}
contained: {int: bool} = {}
own_input = OwnershipTypeInput(&types, &structs, &args, &fields, &variants, &fns, &decls, &copies, &moves, &contained, &parents, &math_id)
own_binding = ownership_types_bind(&own_input)
kind = (k: TK, elem: int = 0, bits: int = 0) -> int: add(TypeInfo(kind=k, elem=i32(elem), bits=i32(bits)))
nominal = (name: str, decl: int, fts: int[], boxed: int = -1) -> int:
    t = record(name, [], decl)
    si = int(types[t].st)
    structs[si].fields = i32(fields.len())
    structs[si].nfields = i32(fts.len())
    loop i in [0..fts.len()): fields.push(Field(type=i32(fts[i]), name=2, boxed=i == boxed))
    t
row = (t: int) -> str:
    "{t}:{ownership_nominal(t)}:{ownership_type(t)}:{ownership_contains(t)}:{ownership_copyable(t)}:{ownership_inline(t)}:{ownership_layout(t)}:{ownership_fact_type(t)}:{ownership_callable_cap(t)}:{ownership_decl_copyable(t)}:{ownership_scalar(t)}:{ow_scalar(t)}"
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
    math_id = add(TypeInfo(kind=.int_, rep=.tagged_int, size=8, align=8, flags=2))
    flt = add(TypeInfo(kind=.float_, bits=64, size=8, align=8, flags=2))
    ref_int = kind(.refined, 1)
    res = nominal("Res", 50, [1])
    structs[int(types[res].st)].drop_fn = 7
    cop = nominal("Cop", 60, [1, 3])
    hook = fns.len()
    fns.push(FnInst(ret=i32(cop)))
    mov = nominal("Mov", 61, [1])
    plain = nominal("Plain", 0, [1, 3, flt])
    arr_int = kind(.array, 1)
    holder = nominal("Holder", 0, [res, 1])
    texty = nominal("Texty", 0, [res, 2, arr_int])
    boxed = nominal("Boxed", 0, [res], 0)
    arr_res = kind(.array, res)
    fix_res = kind(.fixed, res, 3)
    opt_res = kind(.opt, res)
    box_res = kind(.box, res)
    var_res = add(TypeInfo(kind=.var, ref=i32(res), flags=1))
    tup_start = args.len()
    args.push(i32(res)); args.push(1)
    tup = add(TypeInfo(kind=.tuple, args=i32(tup_start), nargs=2))
    variants = [Variant(fields=i32(fields.len()), nfields=1)]
    fields.push(Field(type=i32(res), name=2))
    en = record("Choice", [], 0)
    types[en].kind = .enum_
    structs[int(types[en].st)].nfields = 0; structs[int(types[en].st)].nvariants = 1; structs[int(types[en].st)].variants = 0
    map = nominal("Map", 0, [arr_res, 2])
    child = nominal("Child", 71, [1])
    parents[child] = res
    copy_child = nominal("CopyChild", 72, [res])
    parents[copy_child] = cop
    loop_t = nominal("Loop", 0, [1])
    opt_loop = kind(.opt, loop_t)
    fields[int(structs[int(types[loop_t].st)].fields)].type = i32(opt_loop)
    calls: int[]
    loop cap in [0..5): calls.push(kind(.callable, 1, cap))
    arr_cop = kind(.array, cop)
    all = [1, 2, 3, flt, math_id, ref_int, res, cop, mov, plain, arr_int, holder, texty, boxed, arr_res, fix_res, opt_res, box_res, var_res, tup, en, map, child, copy_child, loop_t, opt_loop, arr_cop] + calls
    # No lifecycle declaration: every resource query takes its early out.
    loop t in all: print(row(t))
    decls[50 * 4 + 1] = 1
    decls[60 * 4 + 2] = hook
    decls[61 * 4 + 3] = 2
    copies[cop] = hook
    copies[copy_child] = hook
    moves[mov] = 2
    loop t in all: print(row(t))
    print(contained)
    print("res={row(res)}")
    print("cop={row(cop)}")
    contained.clear()
    loop i in [0..all.len()): print(row(all[all.len() - 1 - i]))
    print(ownership_declared(50), ownership_declared(61), ownership_declared(71))
    print(ownership_layout(res, 33), ownership_inline(holder, 33), ownership_fact_type(child, 33))
    print(ownership_copyable(holder, [int(holder)]), ownership_layout(holder, 0, [int(holder)]), ownership_decl_copyable(res, [int(res)]))
    print(types.len(), structs.len(), fields.len())
    print(property_events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_ownership_types_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in STEMS:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in STEMS) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
    # A drop hook makes a move-only nominal owner; a copy hook makes it copyable.
    assert b'\nres=28:true:true:true:false:' in outputs[0]
    assert b'\ncop=29:true:true:true:true:' in outputs[0]
