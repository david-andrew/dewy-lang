"""Read-only captures preserve an owner's storage during a local place loan."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT/'tests/fixtures/captured_owner_place.dewy').read_text()
CASES = [SOURCE, (ROOT/'tests/fixtures/captured_resource_place.dewy').read_text(),
    '''make=():>array<int64>=>{let values:array<int64>=[42]
read=():>array<int64>=>values
return read()}
probe=():>int64=>{let result=make() return if result.length>?0 result[0] else 1}
main=():>int64=>{if probe() not=?42 return 1
let before:int64=_arena_live_bytes
loop i in [0..100) {if probe() not=?42 return 2}
$runtime_assert _arena_live_bytes=?before
return 42}''',
    '''Box:type=[items:array<int64>]
make=():>Box=>{let box=Box[[42]]
read=():>Box=>box
return read()}
probe=():>int64=>{let result=make() return if result.items.length>?0 result.items[0] else 1}
main=():>int64=>{if probe() not=?42 return 1
let before:int64=_arena_live_bytes
loop i in [0..100) {if probe() not=?42 return 2}
$runtime_assert _arena_live_bytes=?before
return 42}''',
    '''let values:array<int64>=[0]
read=():>int64=>if values.length>?0 values[0] else 1
main=():>int64=>{values.clear values.push(0)
if values.length=?0 return 1
let cursor=@values[0] cursor=42 return read()}''',
    '''main=():>int64=>{let value:int64=0
read=():>int64=>value
let cursor=@value cursor=42 return read()}''',
    '''Box:type=[value:int64]
main=():>int64=>{let box=Box[0]
read=():>int64=>box.value
let cursor=@box.value cursor=42 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[0]
read=(value:int64=values[0]):>int64=>value
let cursor=@values[0] cursor=42 return read()}''',
    '''use=(values:array<int64 length=1>):>int64=>{
read=():>int64=>values[0]
let cursor=@values[0] cursor=42 return read()}
main=():>int64=>use([0])''',
    '''main=():>int64=>{let values:array<int64>=[0]
read=():>int64=>values[0]
outer=():>int64=>read()
let cursor=@values[0] cursor=42 return outer()}''',
    '''main=():>int64=>{let values:array<int64>=[0]
read=():>int64=>values[0]
let cursor=@values[0]
loop i in [0..42) {cursor+=1 if read()<?0 return 1}
return read()}''',
    '''main=():>int64=>{let values:array<int64>=[0]
read=():>int64=>if values.length>?0 values[0] else 1
let cursor=@values[0] cursor=1
values.clear values.push(42)
return read()}''',
    '''main=():>int64=>{let values:dict<int64 int64>=[1 -> 0]
read=():>int64=>values.get(1 default=0)
if 1 not in? values return 1
let cursor=@values[1] cursor=42 return read()}''',
    # A captured alias conservatively keeps its loan through the whole scope.
    '''main=():>int64=>{let values:array<int64>=[0]
let cursor=@values[0] read=():>int64=>cursor
cursor=42 return read()}''',
    '''let drops:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{drops+=1}]
probe=():>int64=>{let values:array<Handle>=[Handle[0]]
let cursor=@values[0]
read=():>int64=>cursor.id
cursor=Handle[42] return read()}
main=():>int64=>{let answer=probe() return if drops=?2 answer else 1}''',
    '''main=():>int64=>{let values:array<int64>=[0]
let cursor=@values[0] read=(value:int64=cursor):>int64=>value
cursor=42 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[0 1]
let index:int64=0 let cursor=@values[index]
read=():>int64=>cursor
index=1 cursor=42 return read()}''',
    '''main=():>int64=>{let table:dict<int64 int64>=[1->0]
let cursor=@table[1]
read=():>int64=>cursor
cursor=42 return read()}''',
    '''main=():>int64=>{let value:int64=0 let cursor=@value
read=():>int64=>cursor
forward=():>int64=>read()
cursor=42 return forward()}''',
    '''main=():>int64=>{let values:array<int64>=[0]
let cursor=@values[0] let next=@cursor
read=():>int64=>next
cursor=42 return read()}''',
]
ERRORS = [
    '''Handle=type of [id:int64 $__drop__ release=():>void=>{}]
main=():>int64=>{let value=Handle[42]
steal=():>Handle=>value
let other=steal() return other.id}''',
    '''Handle=type of [id:int64 $__drop__ release=():>void=>{}]
main=():>int64=>{let value=Handle[0]
write=():>void=>{value.id=42}
write() return value.id}''',
    '''main=():>int64=>{let values:array<int64>=[0]
let cursor=@values[0] read=():>int64=>cursor
values.clear values.push(42) return read()}''',
    '''main=():>int64=>{let values:array<int64>=[0]
let cursor=@values[0] let next=@cursor
read=():>int64=>next
values.clear values.push(42) return read()}''',
    '''main=():>int64=>{let value:int64=0 let cursor=@value
write=():>void=>{cursor=42}
write() return value}''',
    '''main=():>int64=>{let values:array<int64>=[0]
let cursor=@values read=():>int64=>{let raw=cursor transmute int64 return raw}
cursor.push(42) return read()}''',
    '''main=():>int64=>{let value:int64=42 let cursor=@value
read=():>int64=>cursor
let escaped=@read return escaped()}''',
    '''main=():>int64=>{let values:array<int64>=[0]
change=():>void=>{values.clear}
let cursor=@values[0] change() cursor=42 return cursor}''',
    '''main=():>int64=>{let values:array<int64>=[0]
change=():>void=>{values.clear}
indirect=():>void=>change()
let cursor=@values[0] indirect() cursor=42 return cursor}''',
    '''main=():>int64=>{let values:array<int64>=[0]
read=():>int64=>values[0]
let cursor=@values[0] values.clear cursor=42 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[0]
read=():>int64=>values[0]
let cursor=@values[0] let address=values transmute int64
cursor=42 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[1]
read=():>int64=>values[0]
let cursor=@values[0] cursor=0
return 42//read()}''',
]


@pytest.mark.parametrize('source', CASES)
def test_read_only_captured_owner(tmp_path, source):
    execute(tmp_path, 'captured-owner', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_captured_place_lifetime_still_checked(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_captured_owner_places(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])


def test_native_captured_place_rejections(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    # Escaping/writable captures retain their existing unsupported diagnostic;
    # the other cases fail their storage or numeric proof obligations.
    driver = build_program_driver(tmp_path)
    for index, source in enumerate(ERRORS):
        path = tmp_path/f'error-{index}.dewy'
        path.write_text(source)
        with pytest.raises(ReportException):
            codegen(SrcFile.from_path(path), debug_locations=False)
        result = subprocess.run([driver, path, ROOT/'library', tmp_path/'cache'],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 1 and 'Error' in result.stderr, result.stderr
