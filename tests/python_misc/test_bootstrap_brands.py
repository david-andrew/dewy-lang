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
    let nodes:types.Table = types.Table[]
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
    # A second numbering observes newly registered children, while numbering
    # a saved registry still describes that earlier independent forest.
    let saved=registry
    let late=types.object_type([] 'Late' false [] [] @nodes minted=true parent=right)
    brands.register(late @registry nodes)
    let updated=brands.numbered(registry)
    let before=brands.numbered(saved)
    $runtime_assert updated.length =? 6 and before.length =? numbered.length
    loop i in 0.. and i <? before.length and i <? numbered.length {{
        $runtime_assert before[i].name =? numbered[i].name
        $runtime_assert before[i].first =? numbered[i].first and before[i].end =? numbered[i].end
    }}
    loop entry in updated {{
        if entry.name =? 'Root' {{$runtime_assert entry.first =? 1 and entry.end =? 6}}
        if entry.name =? 'Other' {{$runtime_assert entry.first =? 6 and entry.end =? 7}}
    }}
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
    assert list(actual) == list(ty.brand_ids())  # stable postorder, not just intervals
    assert order.splitlines() == [','.join(ty.brand_children('Root')), ','.join(ty.brand_descendants('Root')),
                                  ','.join(ty.brand_ancestry('Grand')), ty.brand_root('Grand'),
                                  'Grand,Right,Left,Other,Root', 'false', 'true']
