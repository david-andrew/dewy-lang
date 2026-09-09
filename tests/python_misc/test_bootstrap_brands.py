"""Native minted-family numbering agrees with the hosted registry."""

import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_brand_registry_numbering_and_order(tmp_path, monkeypatch):
    source = tmp_path / 'brands.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/brands.dewy'}" as brands
main = ():>int64 => {{
    let nodes:array<types.Type> = []
    let registry = brands.Registry[]
    let structure = types.object_type([] none false [] [] @nodes)
    let root = types.object_type([] 'Root' false [] [] @nodes minted=true parent=structure abstract=true)
    let left = types.object_type([] 'Left' false [] [] @nodes minted=true parent=root)
    let right = types.object_type([] 'Right' false [] [] @nodes minted=true parent=root)
    let grand = types.object_type([] 'Grand' false [] [] @nodes minted=true parent=left)
    let other = types.object_type([] 'Other' false [] [] @nodes minted=true parent=structure)
    loop id in [root left right grand other] {{ brands.register(id @registry nodes) }}
    let numbered = brands.numbered(registry)
    loop entry in numbered {{ printl("{{entry.name}}:{{entry.first}}:{{entry.end}}") }}
    printl('--order--')
    printl(brands.children('Root' registry).join(','))
    printl(brands.descendants('Root' registry).join(','))
    printl(brands.ancestry('Grand' registry).join(','))
    printl(brands.root('Grand' registry))
    printl(brands.most_specific_first(['Other' 'Root' 'Right' 'Left' 'Grand'] registry).join(','))
    printl(brands.concrete('Root' registry))
    printl(brands.concrete('Left' registry))
    return 0
}}
''')
    output = tmp_path / 'brands.udewy'
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], check=True, capture_output=True, text=True, timeout=30)
    numbering, order = result.stdout.split('--order--\n')
    actual = {name: (int(first), int(end)) for name, first, end in (line.split(':') for line in numbering.splitlines())}

    monkeypatch.setattr(ty, 'USER_BRAND_TYPES', {name: ty.ObjectType((), brand=name) for name in ['Root', 'Left', 'Right', 'Grand', 'Other']})
    monkeypatch.setattr(ty, 'USER_BRAND_PARENTS', {'Left': 'Root', 'Right': 'Root', 'Grand': 'Left'})
    monkeypatch.setattr(ty, 'USER_ABSTRACT_BRANDS', {'Root'})
    assert actual == ty.brand_ids()
    assert order.splitlines() == [','.join(ty.brand_children('Root')), ','.join(ty.brand_descendants('Root')),
                                  ','.join(ty.brand_ancestry('Grand')), ty.brand_root('Grand'),
                                  'Grand,Right,Left,Other,Root', 'false', 'true']
