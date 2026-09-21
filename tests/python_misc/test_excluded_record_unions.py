"""Exclusions select logical alternatives, never a different record layout."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
NAMES = ['excluded_record_union', 'excluded_record_resource_union']
PREFIX = 'let Base=type of [value:int64]\nlet Child=type of Base & [extra:int64]\nChoice:type=(Base & ~Child)|Child\n'
CASES = [
    '$no_prelude=true\n'+PREFIX+
    'main=():>int64=>{let item:Choice=Base[42] if item is? Child return 1 return item.value}',
    'let Base=type of [items:array<int64 length=2>]\nlet Child=type of Base & [extra:int64]\n'
    'Choice:type=(Base & ~Child)|Child\n'
    'main=():>int64=>{let item:Choice=Base[[40 2]] let saved=item.copy() '
    'if saved isnt? Child {saved.items[0]=99} if item isnt? Child return item.items[0]+item.items[1] return 1}',
    PREFIX+'let Other=type of Base & [padding:int64]\nlet Sibling=type of Base & [unused:int64 extra:int64]\n'
    'read=(item:(Base & ~Other)|Other):>int64=>{if item is? Child|Sibling return item.value+item.extra return 0}\n'
    'main=():>int64=>if read(Child[40 2])=?42 and read(Sibling[40 999 2])=?42 42 else 1',
    PREFIX+'let Other=type of Base & [padding:int64]\n'
    'main=():>int64=>{let item:(Base & ~Other)|Other=Child[40 2] if item isnt? Other {if item is? Child return item.value+item.extra} return 1}',
    PREFIX+'make=(flag:bool):>Base=>if flag Child[40 2] else Base[42]\n'
    'let run=(flag:bool):>int64=>{let parent=make(flag) let item:Choice=parent if item is? Child return item.value+item.extra return item.value}\n'
    'main=():>int64=>if run(true)=?42 and run(false)=?42 42 else 1',
    PREFIX+'main=():>int64=>{let item:Choice=Base[1] if item isnt? Child {item.value=42 return item.value} return 1}',
    PREFIX+'main=():>int64=>{let parent:Choice=Base[42] if parent isnt? Child {let item:(Base & ~Child)?=parent if item isnt? none return item.value} return 1}',
]
ERRORS = [
    'let Base=type of [value:int64 $__drop__ release=():>void=>{}]\n'
    'let Child=type of Base & [extra:int64]\n'
    'main=():>int64=>{let item:(Base & ~Child)|Child=Base[42] let saved=item.copy() return 42}',
    PREFIX+'f=(item:Base & ~Child):>int64=>item.extra',
    PREFIX+'f=(item:Base & ~Child):>int64=>{let n=item.value $assert item is? Child return n}',
]


@pytest.mark.parametrize('name', NAMES)
def test_stored_excluded_record_family(tmp_path, name):
    execute(tmp_path, name, codegen(SrcFile.from_path(ROOT / f'tests/fixtures/{name}.dewy'), debug_locations=False))


@pytest.mark.parametrize('source', CASES)
def test_family_storage_paths(tmp_path, source):
    execute(tmp_path, 'family-path', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_exclusions_are_preserved_by_member_reads(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_excluded_record_family(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[*( (ROOT/f'tests/fixtures/{name}.dewy').read_text() for name in NAMES), *CASES],
                          errors=ERRORS)
