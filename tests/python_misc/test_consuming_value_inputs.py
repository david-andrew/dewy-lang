"""Single-use aggregate inputs transfer into returned values and constructors."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

BASE = '''$explicit_copies
Box:type=[items:array<int64>]
wrap=(items:array<int64>):>Box=>Box[items]
make=():>array<int64>=>[42]
work=():>int64=>{
 let value=wrap(make())
 return if value.items.length>?0 value.items[0] else 1
}
main=():>int64=>{
 loop i in [0..1000) {if work() not=?42 return 1}
 let before:int64=_arena_live_bytes
 loop i in [0..1000) {if work() not=?42 return 2}
 return if _arena_live_bytes=?before 42 else 3
}'''
CASES = [BASE,
 BASE.replace('wrap(make())','wrap(items=make())'),
 BASE.replace(' let value=wrap(make())',' let local=make()\n let value=wrap(local)'),
 BASE.replace('make=','forward=(items:array<int64>):>Box=>wrap(items)\nmake=',1).replace('value=wrap(make())','value=forward(make())'),
 BASE.replace('Box[items]','{return Box[items]}'),
 BASE.replace('wrap=(items:array<int64>):>Box=>Box[items]','wrap=(items:array<int64>):>array<int64>=>items').replace('value.items','value'),
 BASE.replace('wrap=(items:array<int64>):>Box=>Box[items]','wrap=(box:Box):>Box=>box').replace('wrap(make())','wrap(Box[make()])'),
 BASE.replace('wrap=(items:array<int64>):>Box=>Box[items]','wrap=(box:Box|none):>Box|none=>box').replace('wrap(make())','wrap(Box[make()])').replace('if value.items.length>?0','if value is? Box and value.items.length>?0'),
 BASE.replace('wrap=(items:array<int64>):>Box=>Box[items]', 'wrap=(items:array<int64>):>array<array<int64>>=>[items]').replace('value.items.length>?0 value.items[0]','value.length>?0 and value[0].length>?0 value[0][0]'),
 BASE.replace(' let value=wrap(make())',' let local=make()\n let value=wrap(local.copy())\n local.clear()'),
]
CASES.extend([
 BASE.replace('wrap=(items:array<int64>):>Box=>Box[items]', 'wrap=(box:Box):>Box?=>box').replace('wrap(make())','wrap(Box[make()])').replace('if value.items.length>?0','if value isnt? none and value.items.length>?0'),
 BASE.replace('wrap=(items:array<int64>):>Box=>Box[items]', 'wrap=(items:array<int64>):>array<int64>=>{items}').replace('value.items','value'),
])
CASES.extend([
 BASE.replace('wrap(make())','wrap([42])'),
 BASE.replace('Box:type=[items:array<int64>]', 'Leaf:type=[values:array<int64>]\nBox:type=[items:array<Leaf>]').replace('wrap=(items:array<int64>)','wrap=(items:array<Leaf>)').replace('wrap(make())','wrap([Leaf[[42]]])').replace('value.items.length>?0 value.items[0]','value.items.length>?0 and value.items[0].values.length>?0 value.items[0].values[0]'),
])
CASES.append(BASE.replace('wrap=(items:array<int64>):>Box=>Box[items]',
    'Holder:type=[box:Box]\nwrap=(box:Box):>Holder=>Holder[box]').replace('wrap(make())','wrap(Box[make()])').replace('value.items','value.box.items'))
ERRORS = [
 BASE.replace(' let value=wrap(make())',' let local=make()\n let value=wrap(local)\n local.clear()'),
 BASE.replace('Box[items]','{let extra=items return Box[items]}'),
 BASE.replace('Box[items]','if items.length>?0 Box[items] else Box[[]]'),
 BASE.replace(' let value=wrap(make())',' let callback=@wrap\n let value=callback(make())'),
]

@pytest.mark.parametrize('source', CASES)
def test_consuming_value_input(tmp_path, source):
    execute(tmp_path,'consume-value',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_consuming_value_input_keeps_snapshots(source):
    with pytest.raises(ReportException,match='unproven copy'):
        codegen(SrcFile(None,source),debug_locations=False)


def test_native_consuming_value_inputs(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)


def test_forwarding_cycle_is_not_ownership_evidence():
    from dewy.semantic.check import typecheck_and_resolve
    from dewy.semantic.analyze.effects import _EffectAnalyzer
    from dewy.backend.udewy.consuming_inputs import parameters
    root=typecheck_and_resolve(SrcFile(None, """
cycle_a=(items:array<int64>):>array<int64>=>cycle_b(items)
cycle_b=(items:array<int64>):>array<int64>=>cycle_a(items)
"""), include_prelude=False)
    assert not parameters(_EffectAnalyzer(root), set())
