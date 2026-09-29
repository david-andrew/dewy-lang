"""A member-to-union conversion has the same ownership cost as any store."""
import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute


ERRORS = [
    '''Box:type=[items:array<int64>]
find=(rows:array<Box>):>Box?=>{loop row in rows {return row} return none}
main=():>int64=>42''',
    '''Box:type=[items:array<int64>]
wrap=(box:Box):>Box?=>if box.items.length>?0 box else none
main=():>int64=>42''',
    '''wrap=(values:array<int64>):>array<int64> ?=>if values.length>?0 values else none
main=():>int64=>42''',
    '''Box:type=[items:array<int64>]
wrap=(values:array<Box length=1>):>array<Box length=1> ?=>values
main=():>int64=>42''',
]

CASES = [
    '''Box:type=[items:array<int64>]
make=():>Box?=>Box[[42]]
forward=():>Box?=>{let value=make() if value isnt? none return value return none}
probe=():>int64=>{let result=forward()
if result isnt? none and result.items.length>?0 return result.items[0]
return 1}
main=():>int64=>{if probe() not=?42 return 1
let before:int64=_arena_live_bytes
loop i in [0..100) {if probe() not=?42 return 2}
$runtime_assert _arena_live_bytes=?before
return 42}''',
    '''Box:type=[items:array<int64>]
probe=():>int64=>{let box=Box[[42]] let result:Box?=box
if result isnt? none and result.items.length>?0 return result.items[0]
return 1}
main=():>int64=>{if probe() not=?42 return 1
let before:int64=_arena_live_bytes
loop i in [0..100) {if probe() not=?42 return 2}
$runtime_assert _arena_live_bytes=?before
return 42}''',
    '''make=():>array<int64>=>[42]
probe=():>int64=>{let values=make() let result:array<int64> ?=values
if result isnt? none and result.length>?0 return result[0]
return 1}
main=():>int64=>{if probe() not=?42 return 1
let before:int64=_arena_live_bytes
loop i in [0..100) {if probe() not=?42 return 2}
$runtime_assert _arena_live_bytes=?before
return 42}''',
    '''Box:type=[items:array<int64>]
wrap=(box:Box):>Box?=>box.copy()
main=():>int64=>{let box=Box[[42]] let result=wrap(box)
box.items.clear()
if result isnt? none and result.items.length>?0 return result.items[0]
return 1}''',
    '''wrap=(values:array<int64>):>array<int64> ?=>values.copy()
main=():>int64=>{let values:array<int64>=[42] let result=wrap(values)
values.clear()
if result isnt? none and result.length>?0 return result[0]
return 1}''',
]


@pytest.mark.parametrize('source', ERRORS)
def test_union_injection_is_reported_and_enforced(source):
    codegen(SrcFile(None, source), debug_locations=False)
    notes = [note for note in lower.last_copy_notes if note.srcfile.path is None]
    assert any(note.runtime_sized and not note.explicit and not note.policy_exempt
               for note in notes)
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n'+source), debug_locations=False)


@pytest.mark.parametrize('source', CASES)
def test_union_injection_transfers_and_explicit_snapshots(tmp_path, source):
    execute(tmp_path, 'injection', codegen(SrcFile(None, '$explicit_copies\n'+source),
                                         debug_locations=False))


def test_native_union_injection_copies(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=['$explicit_copies\n'+source for source in CASES],
                          errors=['$explicit_copies\n'+source for source in ERRORS])
