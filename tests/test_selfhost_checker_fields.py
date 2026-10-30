"""Recursive field publication preserves scopes, arena snapshots and frozen order."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_type_unions import DRIVER as UNION_DRIVER

DRIVER = UNION_DRIVER.split('main = ():')[0] + r'''
nodes: Node[] = [Node()]
lists: i32[]
components: {int: int[]} = {}
parts: {int: int[]} = {}
parents: {int: int} = {}
binders = RefineBindings()
active = true
depth = 0
nested = 0
field_grew = false
snapshot_fields: Field[]
enter_fields = (d: int, si: int) -> CheckerFieldScope:
    events.push("enter:{d}:{si}:{depth}")
    assert(structs[si].resolved)
    cf_check_struct_fields(si)
    saved = depth
    depth += 1
    CheckerFieldScope(saved, d)
leave_fields = (scope: CheckerFieldScope):
    assert(depth == scope.context + 1)
    depth = scope.context
    events.push("leave:{scope.mark}:{depth}")
resolve_field_type = (n: int) -> int:
    events.push("resolve:{n}:{depth}")
    if not field_grew:
        field_grew = true
        snapshot_fields = fields
        loop i in [0..128):
            nodes.push(Node()); lists.push(0); types.push(TypeInfo()); structs.push(StructInfo())
            fields.push(Field()); variants.push(Variant())
        saved = binders.fields
        cf_check_struct_fields(nested)
        assert(binders.fields == saved, "nested field binder restoration")
    int(nodes[n].ival)
default_field_type = (f: int, si: int, before: int) -> int:
    events.push("default:{f}:{si}:{before}:{binders.fields}")
    1
exit_name = () -> int: 99
exit_field = (t: int, f: int, st: int, d: int) -> int:
    events.push("exit:{t}:{f}:{st}:{d}")
    t
map_type = (t: int) -> bool: false
validate_fields = (t: int, pos: int): events.push("validate:{t}:{pos}:{binders.fields}")
field_error = (kind: int, n: int, a: int, b: int):
    print("error:{kind}:{n}:{a}:{b}")
    exit(17)
intersection_error = (pos: int, name: int, a: int, b: int):
    print("intersection:{pos}:{name}:{a}:{b}")
    exit(17)
field_host = CheckerFieldHost(enter_fields, leave_fields, resolve_field_type, default_field_type, exit_name, exit_field, map_type, validate_fields, field_error, intersection_error)
field_binding = checker_fields_bind(&nodes, &lists, &types, &structs, &fields, &variants, &components, &parts, &parents, &binders, &active, &field_host)
node = (kind: NK, a: int = 0, b: int = 0, name: int = 0, value: int = 0, children: int[] = []) -> int:
    n = nodes.len()
    nodes.push(Node(kind=kind, a=i32(a), b=i32(b), name=i32(name), ival=value, list=i32(lists.len()), nlist=i32(children.len()), pos=n))
    loop child in children: lists.push(i32(child))
    n
structure = (decl: int, kind: TK = .struct_) -> int:
    si = structs.len()
    t = types.len()
    structs.push(StructInfo(decl=i32(decl), type=i32(t)))
    types.push(TypeInfo(kind=kind, st=i32(si)))
    si
prepare = ():
    union_reset()
    field_grew = false
    binders.fields = [777]
    nested = structure(node(.struct_, 0, 0, 0, 0, [node(.field, 0, 1, 30)]))
main = ():
    prepare()
    it = node(.tname, 0, 0, 0, 1)
    a = structure(node(.struct_, 0, 0, 0, 0, [node(.field, it, 0, 10), node(.field, 0, 1, 11), node(.field, it, 0, 99)]))
    b = structure(node(.struct_, 0, 0, 0, 0, [node(.field, it, 0, 12)]))
    parents[int(structs[b].type)] = int(structs[a].type)
    cdecl = node(.struct_, 0, 0, 0, 0, [node(.field, it, 123, 10)])
    c = structure(cdecl)
    components[cdecl] = [node(.tname, 0, 0, 0, int(structs[a].type))]
    v1 = node(.variant, node(.int_lit, 0, 0, 0, -1), 0, 20, 0, [node(.field, it, 0, 21)])
    v2 = node(.variant, 0, 0, 22)
    e = structure(node(.enum_, 0, 0, 0, 0, [v1, v2]), .enum_)
    saved_structs = structs
    saved_fields = fields
    saved_variants = variants
    cf_check_struct_fields(b)
    cf_check_struct_fields(c)
    cf_check_struct_fields(e)
    assert(field_grew and depth == 0 and binders.fields == [777])
    assert(not saved_structs[a].resolved and saved_fields.len() == 0 and saved_variants.len() == 0)
    assert(snapshot_fields.len() == 3 and snapshot_fields[0].type == 0 and snapshot_fields[1].type == 0, "published placeholders retain snapshot values")
    assert(structs[a].nfields == 3 and structs[b].nfields == 4 and structs[c].nfields == 3)
    assert(fields[int(structs[c].fields)].defval == 123)
    assert(parts[int(structs[c].type)] == [int(structs[a].type)])
    assert(variants[int(structs[e].variants)].value == -1 and variants[int(structs[e].variants)+1].value == 0)
    count = events.len()
    cf_check_struct_fields(c)
    assert(events.len() == count, "resolved hit does not request host work")
    u = int(uu_mk_union([1, 2, 3])); v = int(uu_mk_union([1, 2]))
    assert(cf_intersect_types(u, v) == v and cf_intersect_types(1, 2) == 0)
    o = optional(1)
    assert(cf_intersect_types(o, 1) == 1 and cf_intersect_types(1, o) == 1)
    loop si in [a, b, c, e, nested]: print(structs[si])
    print(fields); print(variants); print(events)
    print("ok")
'''


def compare(compiler, tmp_path, release, driver, status=0):
    outputs = []
    stems = ('node_store', 'checker_state', 'checker_types', 'checker_tokens', 'refinement_types',
             'refine_predicates', 'refine_queries', 'type_queries', 'type_intern',
             'type_inference', 'type_unions', 'checker_fields')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo': text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + driver)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])], capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == status, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    return outputs[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_fields_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER).endswith(b'ok\n')


@pytest.mark.parametrize('kind,fields,error', [
    ('struct_', '[node(.field, 0, 0, 10)]', 3),
    ('struct_', '[node(.field, it, 0, 10), node(.field, it, 0, 10)]', 4),
    ('enum_', '[node(.variant, it, 0, 10)]', 5),
    ('enum_', '[node(.variant, 0, 0, 10), node(.variant, 0, 0, 10)]', 6),
])
def test_checker_field_errors(compiler, tmp_path, kind, fields, error):  # noqa: F811
    driver = DRIVER.split('main = ():')[0] + f'''main = ():
    prepare()
    it = node(.tname, 0, 0, 0, 1)
    si = structure(node(.{kind}, 0, 0, 0, 0, {fields}), .{kind})
    cf_check_struct_fields(si)
    assert(false)
'''
    assert compare(compiler, tmp_path, False, driver, 17).startswith(f'error:{error}:'.encode())


@pytest.mark.parametrize('minted,error', [(False, 1), (True, 2)])
def test_checker_intersection_errors(compiler, tmp_path, minted, error):  # noqa: F811
    setup = 't = 1'
    if minted:
        setup = "base = structure(node(.struct_))\n    t = int(structs[base].type)\n    parents[t] = 1"
    driver = DRIVER.split('main = ():')[0] + f'''main = ():
    prepare()
    {setup}
    d = node(.struct_)
    si = structure(d)
    components[d] = [node(.tname, 0, 0, 0, t)]
    cf_check_struct_fields(si)
    assert(false)
'''
    assert compare(compiler, tmp_path, False, driver, 17).startswith(f'error:{error}:'.encode())
