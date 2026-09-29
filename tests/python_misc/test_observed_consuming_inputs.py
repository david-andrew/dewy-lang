"""Scalar observations can precede a final transfer; early exits still clean up."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile,ReportException
from test_scalar_projection import execute

SOURCE='''$explicit_copies
Item:type=[size:addr values:array<int64>]
keep=(value:Item):>Item=>{
 if value.size=?0 return Item[0 []]
 return value
}
work=():>int64=>{
 let value=keep(Item[2 [20 22]])
 let empty=keep(Item[0 [99]])
 return if empty.values.length=?0 and value.values.length=?2 value.size+40 else 1
}
main=():>int64=>{
 loop i in [0..100) {if work() not=?42 return 1}
 let before:int64=_arena_live_bytes
 loop i in [0..100) {if work() not=?42 return 2}
 return if _arena_live_bytes=?before 42 else 3
}'''
ARRAY=SOURCE.replace('keep=(value:Item):>Item=>{\n if value.size=?0 return Item[0 []]\n return value\n}',
 'keep=(values:array<int64>):>Item=>{if values.length=?0 return Item[0 []] return Item[values.length values]}').replace('keep(Item[2 [20 22]])','keep([20 22])').replace('keep(Item[0 [99]])','keep([])')
OPTIONAL='''$explicit_copies
Item:type=[size:addr values:array<int64>]
keep=(@out:array<Item> value:Item?):>void=>{
 if value is? none return
 if value.size=?0 return
 out.push(value)
}
work=():>int64=>{
 let out:array<Item>=[]
 keep(@out Item[2 [20 22]])
 keep(@out Item[0 [99]])
 keep(@out none)
 return if out.length=?1 and out[0].values.length=?2 out[0].size+40 else 1
}
'''+ 'main='+SOURCE.split('main=',1)[1]
CASES=[SOURCE,ARRAY,OPTIONAL,
 SOURCE.replace('keep(Item[2 [20 22]])','keep(value=Item[2 [20 22]])'),
 SOURCE.replace('let value=keep(Item[2 [20 22]])','let original=Item[2 [20 22]]\n let value=keep(original.copy())\n original.values.clear()'),
 SOURCE.replace('if value.size=?0 return Item[0 []]', 'loop i in [0..value.size) {let inspected=value.size}\n if value.size=?0 return Item[0 []]'),
]
ERRORS=[SOURCE.replace('let value=keep(Item[2 [20 22]])','let original=Item[2 [20 22]]\n let value=keep(original)\n original.values.clear()'),
 SOURCE.replace('return value\n}', 'let saved=value.values\n return value\n}'),
 SOURCE.replace('let value=keep(Item[2 [20 22]])','let callback=@keep\n let value=callback(Item[2 [20 22]])')]

@pytest.mark.parametrize('source',CASES)
def test_observed_input_cleanup(tmp_path,source):
 execute(tmp_path,'observed-input',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_observed_input_keeps_independent_values(source):
 with pytest.raises(ReportException,match='unproven copy'):
  codegen(SrcFile(None,source),debug_locations=False)


def test_native_observed_inputs(tmp_path):
 from test_bootstrap_structural_text import build_program_driver,check_structural_text
 check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)

CASES.extend([
 ARRAY.replace('keep=(values:array<int64>):>Item=>{', 'keep=(values:array<int64>|none):>Item=>{if values is? none return Item[0 []] '),
 OPTIONAL.replace('Item:type=[','Item=type of ['),
 SOURCE.replace('if value.size=?0 return Item[0 []]', '$runtime_assert value.size<?3\n if value.size=?0 return Item[0 []]'),
])

CASES.append(SOURCE.replace('Item:type=[', 'Item=type of [').replace('keep=(value:Item):>Item', 'Other=type of [size:addr values:array<int64>]\nNode:type=Item|Other\nkeep=(value:Node):>Node').replace('empty.values.length=?0 and value.values.length=?2', 'empty.size=?0 and value.size=?2'))
