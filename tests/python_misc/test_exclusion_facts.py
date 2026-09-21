"""A failed family test is usable evidence at ordinary value boundaries."""
import pytest
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute
PREFIX='let Base=type of [value:int64]\nlet Child=type of Base & [extra:int64]\n'
CASES=[
    (Path(__file__).resolve().parents[2]/'tests/fixtures/exclusion_facts.dewy').read_text(),
    PREFIX+'main=():>int64=>{let parent:Base=Base[42] if parent isnt? Child {let item:(Base & ~Child)?=parent if item isnt? none return item.value} return 1}',
    PREFIX+'read=(item:Base & ~Child):>int64=>item.value\nmain=():>int64=>{let item:Base=Base[42] if item isnt? Child return read(item) return 1}',
    PREFIX+'Box:type=[item:Base]\nmain=():>int64=>{let box=Box[Base[42]] if box.item isnt? Child {let value:Base & ~Child=box.item return value.value} return 1}',
    PREFIX+'main=():>int64=>{let item:Base=Base[1] if item isnt? Child {let copy=item copy=Child[40 2] if copy is? Child return copy.value+copy.extra} return 1}',
    PREFIX+'let Other=type of Base & [padding:int64]\nread=(item:Base & ~Child & ~Other):>int64=>item.value\n'
    'main=():>int64=>{let item:Base=Base[42] if item isnt? Child|Other return read(item) return 1}',
]
CASES += [
    PREFIX+'make=(item:Base & ~Child):>Base & ~Child=>item\nmain=():>int64=>{let original:Base=Base[42] if original isnt? Child {let item=make(original) return item.value} return 1}',
    PREFIX+'change=(item:Base & ~Child):>int64=>{item.value=1 return item.value}\nmain=():>int64=>{let item:Base=Base[42] if item isnt? Child {if change(item) not=?1 return 1 return item.value} return 2}',
    PREFIX+'main=():>int64=>{let item:Base=Base[42] if item isnt? Child {let saved=item.copy() saved.value=1 return item.value} return 2}',
]
CASES += [
    PREFIX+'let Other=type of Base & [unused:int64]\n'
    'read=(item:Base):>int64=>{if item is? Child return 0 let ignored:int64=0 if item is? Other {ignored=1} return item.value}\n'
    'main=():>int64=>if read(Base[42])=?42 and read(Other[42 7])=?42 42 else 1',
    PREFIX+'let Other=type of Base & [unused:int64]\n'
    'read=(item:Base):>string=>{if item isnt? Child return item.typename return "Child"}\n'
    'main=():>int64=>if read(Base[42])=?"Base" and read(Other[42 7])=?"Other" 42 else 1',
    PREFIX+'let Other=type of Base & [unused:int64]\n'
    'read=(item:Base):>int64=>{if item isnt? Child {if typeof(item) is? Other return item.value} return 1}\n'
    'main=():>int64=>read(Other[42 7])',
]
ERRORS=[
    PREFIX+'main=():>int64=>{let item:Base=Base[1] if item isnt? Child {item=Child[40 2] let saved:Base & ~Child=item return saved.value} return 42}',
    PREFIX+'Box:type=[item:Base]\nmain=():>int64=>{let box=Box[Base[1]] if box.item isnt? Child {box.item=Child[40 2] let saved:Base & ~Child=box.item return saved.value} return 42}',
    PREFIX+'main=():>int64=>{let item:Base=Base[42] if item isnt? Child {} let saved:Base & ~Child=item return saved.value}',
]
@pytest.mark.parametrize('source',CASES)
def test_exclusion_at_value_boundary(tmp_path,source):
    execute(tmp_path,'exclusion',codegen(SrcFile(None,source),debug_locations=False))
@pytest.mark.parametrize('source',ERRORS)
def test_exclusion_does_not_survive_mutation_or_join(source):
    with pytest.raises(ReportException): codegen(SrcFile(None,source))
def test_native_exclusion_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
