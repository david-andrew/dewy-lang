"""Native aggregate offsets and element strides match the hosted ABI."""
import subprocess
from pathlib import Path

from test_bootstrap_initialization import type_builder
from dewy.backend.udewy import codegen
from dewy.backend.udewy.lower import _Lowerer
from dewy.reporting import Span, SrcFile
from dewy.semantic import hir, ty
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_aggregate_layouts(tmp_path, monkeypatch):
    monkeypatch.setattr(ty, 'USER_BRAND_TYPES', {})
    monkeypatch.setattr(ty, 'USER_BRAND_PARENTS', {})
    monkeypatch.setattr(ty, 'USER_BRANDS', set())
    node = hir.Void(Span(0, 0), 'void')
    lowerer = object.__new__(_Lowerer)
    field = ty.ObjectField
    record = lambda *fields: ty.ObjectType(tuple(fields))
    pair = record(field('small', 'uint8'), field('wide', 'uint64'))
    function = ty.FunctionType([], [], None, 'int64')
    optional = ty.optional('int64')
    union = ty.union('int64', 'string')
    records = [
        record(), record(field('flag', 'bool')),
        pair, record(field('wide', 'uint64'), field('small', 'uint8')),
        record(field('head', 'bool'), field('pair', pair), field('tail', 'uint8')),
        record(field('items', ty.ArrayType('int64')), field('text', 'string')),
        record(field('call', function), field('maybe', optional), field('choice', union)),
    ]
    elements = ['bool', 'int8', 'uint8', 'int64', 'uint64', 'string', pair,
                ty.ArrayType('uint8'), function, optional, union]
    lines, checks, expected = [], [], []
    build = type_builder(lines)
    for index, type_ in enumerate(records):
        size, offsets = lowerer._object_layout(type_, node)
        description = ';'.join(f'{name}:{offset}' for name, offset in offsets.items())
        checks.append(f'    printl("record-{index}|{{record_text(layouts.record({build(type_)} context @type_nodes))}}")')
        expected.append(f'record-{index}|{size}|{description}')
    for index, type_ in enumerate(elements):
        size, signed = lowerer._array_element_layout(type_, node)
        checks.append(f'    printl("element-{index}|{{element_text(layouts.element({build(type_)} @type_nodes))}}")')
        expected.append(f'element-{index}|{size}|{str(signed).lower()}')
    checks.append(f'    printl(layouts.element({build("int")} @type_nodes) is? layouts.Pending)')
    expected.append('true')
    base = record(field('flag', 'bool'))
    root = ty.ObjectType(base.fields, brand='Root')
    child = ty.ObjectType((*base.fields, field('wide', 'uint64')), brand='Child')
    holder = record(field('head', 'uint8'), field('root', root), field('tail', 'uint8'))
    monkeypatch.setattr(ty, 'USER_BRAND_TYPES', {'Root': root, 'Child': child})
    monkeypatch.setattr(ty, 'USER_BRAND_PARENTS', {'Child': 'Root'})
    monkeypatch.setattr(ty, 'USER_BRANDS', {'Root', 'Child'})
    branded = f"""
    let base={build(base)}
    let base_node=types.node_at(type_nodes base)
    $runtime_assert base_node is? types.ObjectType
    let root=types.object_type(base_node.fields 'Root' false [] [] @type_nodes minted=true parent=base)
    let fields=base_node.fields
    fields.push(types.ObjectField['wide' {build('uint64')}])
    let child=types.object_type(fields 'Child' false [] [] @type_nodes minted=true parent=root)
    let holder=types.object_type([types.ObjectField['head' {build('uint8')}] types.ObjectField['root' root] types.ObjectField['tail' {build('uint8')}]] none false [] [] @type_nodes)
    let registry=brands.Registry[]
    brands.register(root @registry type_nodes)
    brands.register(child @registry type_nodes)
    let family=layouts.Context[registry]
    loop id in [base root child holder] {{printl("brand|{{record_text(layouts.record(id family @type_nodes))}}")}}
"""
    for type_ in [base, root, child, holder]:
        size, offsets = lowerer._object_layout(type_, node)
        description = ';'.join(f'{name}:{offset}' for name, offset in offsets.items())
        expected.append(f'brand|{size}|{description}')
    source = tmp_path / 'layouts.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/brands.dewy'}" as brands
import p"{ROOT / 'dewy/bootstrap/backend/udewy/layouts.dewy'}" as layouts
record_text = (value:layouts.Record|layouts.Pending):>string => {{
    if value is? layouts.Pending return value.detail
    let parts:array<string>=[]
    loop [name offset] in value.offsets {{parts.push("{{name}}:{{offset}}")}}
    return "{{value.size}}|{{parts.join(';')}}"
}}
element_text = (value:layouts.Storage|layouts.Pending):>string => {{
    if value is? layouts.Pending return value.detail
    return "{{value.size}}|{{value.signed}}"
}}
main = ():>int64 => {{
    let type_nodes:array<types.Type>=[]
    let context=layouts.Context[]
{chr(10).join(lines)}
{chr(10).join(checks)}
{branded}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
