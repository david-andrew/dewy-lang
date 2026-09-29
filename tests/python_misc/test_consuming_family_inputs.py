"""Donated ancestor values retain and release all dynamic descendant fields."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

BASE = '''$explicit_copies
Node=type of any & [tag:int64]
Leaf=type of Node & [items:array<int64>]
append=(value:Node @rows:array<Node>):>void=>{rows.push(value)}
make=():>Node=>Leaf[0 [42]]
work=():>int64=>{
 let rows:array<Node>=[]
 let value=make()
 append(value @rows)
 if rows.length>?0 {
  const item=@rows[0]
  if item is? Leaf and item.items.length>?0 return item.items[0]
 }
 return 1
}
main=():>int64=>{
 loop i in [0..100) {if work() not=?42 return 1}
 let before:int64=_arena_live_bytes
 loop i in [0..100) {if work() not=?42 return 2}
 return if _arena_live_bytes=?before 42 else 3
}'''
CASES = [BASE,
 BASE.replace('Leaf=type of Node & [items:array<int64>]',
              'Part:type=[items:array<int64>]\nLeaf=type of Node & [part:Part]').replace('Leaf[0 [42]]','Leaf[0 Part[[42]]]').replace('item.items','item.part.items'),
 BASE.replace('items:array<int64>', 'items:array<int64>|none').replace('if item is? Leaf and item.items.length>?0','if item is? Leaf and item.items isnt? none and item.items.length>?0'),
 BASE.replace('Leaf=type of Node & [items:array<int64>]',
              'Part:type=[items:array<int64>]\nLeaf=type of Node & [part:Part?]').replace('Leaf[0 [42]]','Leaf[0 Part[[42]]]').replace('if item is? Leaf and item.items.length>?0 return item.items[0]',
              'if item is? Leaf and item.part isnt? none and item.part.items.length>?0 return item.part.items[0]'),
]
# Inline cells must also remain safe to clean up when the active payload is
# absent or an immutable string, rather than an aggregate handle.
CASES.extend([
 BASE.replace('items:array<int64>', 'items:array<int64>|none').replace('Leaf[0 [42]]', 'Leaf[0 none]').replace('if item is? Leaf and item.items.length>?0 return item.items[0]', 'if item is? Leaf and item.items is? none return 42'),
 BASE.replace('items:array<int64>', 'items:array<int64>|string|none').replace('Leaf[0 [42]]', 'Leaf[0 "answer"]').replace('if item is? Leaf and item.items.length>?0 return item.items[0]', 'if item is? Leaf and item.items is? string and item.items=?"answer" return 42'),
])
# A retained original needs an independent value despite descendant dispatch.
ERROR = BASE.replace(' append(value @rows)', ' append(value @rows)\n if value is? Leaf {value.items.clear()}')
CASES.append(ERROR.replace('append(value @rows)', 'append(value.copy() @rows)'))

@pytest.mark.parametrize('source', CASES)
def test_consuming_family_input(tmp_path, source):
    execute(tmp_path, 'family-transfer', codegen(SrcFile(None, source), debug_locations=False))


def test_consuming_family_retained_source():
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, ERROR), debug_locations=False)


def test_native_consuming_family_inputs(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[ERROR])
