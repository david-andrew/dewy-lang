"""A dying record can transfer an owned array while cleaning its other fields."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER = '''Pack:type=[values:array<int64> other:array<string>]
make=():>Pack=>{
 let values:array<int64>=[2]
 values.reserve(8)
 return Pack[values ['left behind']]
}
read=(values:array<int64>):>int64=>if values.length>?1 values[0]+values[1] else 0
'''
LOCAL = HEADER + '''exercise=():>int64=>{
 let owner=make()
 let before:int64=_arena_allocated_bytes
 let values=owner.values
 values.push(40)
 let allocated:int64=_arena_allocated_bytes-before
 return if allocated=?0 read(values) else 1
}
main=():>int64=>{
 if exercise() not=?42 return 1
 let before:int64=_arena_live_bytes
 loop i in [0..50) {if exercise() not=?42 return 2}
 return if _arena_live_bytes=?before 42 else 3
}'''
RETURN = HEADER + '''take=():>array<int64>=>{let owner=make() return owner.values}
main=():>int64=>{let values=take() values.push(40) return read(values)}'''
NESTED = LOCAL.replace('let owner=make()', 'let owner=[inside=make()]').replace('owner.values', 'owner.inside.values')
STORE = HEADER + '''main=():>int64=>{
 let owner=make()
 let target=Pack[owner.values []]
 target.values.push(40)
 return read(target.values)
}'''
LIVE = LOCAL.replace('let allocated:int64=', 'if owner.values.length not=?1 return 0\n let allocated:int64=').replace('allocated=?0', 'allocated>=?0')
VIEW = LOCAL.replace('let before:int64=', 'const held=@owner.values\n let before:int64=', 1).replace('let allocated:int64=', 'if held.length not=?1 return 0\n let allocated:int64=').replace('allocated=?0', 'allocated>=?0')
LOOP = HEADER + '''main=():>int64=>{
 let owner=make()
 loop i in [0..2) {let values=owner.values values.push(40) if read(values) not=?42 return 0}
 return 42
}'''
SHARED = LOCAL.replace('let before:int64=', 'let snapshot=owner.values.copy()\n let before:int64=', 1).replace('let allocated:int64=', 'if snapshot.length not=?1 return 0\n let allocated:int64=').replace('allocated=?0', 'allocated>=?0')
SHARED_RECORD = LOCAL.replace('let before:int64=', 'let snapshot=owner.copy()\n let before:int64=', 1).replace('let allocated:int64=', 'if snapshot.values.length not=?1 or snapshot.other.length not=?1 return 0\n let allocated:int64=').replace('allocated=?0', 'allocated>=?0')
CONST_RECORD = SHARED_RECORD.replace('let owner=make()', 'const owner=make()')
CALL = RETURN.replace('take=():>array<int64>=>{let owner=make() return owner.values}',
 'keep=(values:array<int64>):>array<int64>=>values\ntake=():>array<int64>=>{let owner=make() return keep(owner.values)}')
BRANCH = RETURN.replace('take=():>array<int64>=>{let owner=make() return owner.values}',
 'take=(which:bool):>array<int64>=>{let owner=make() if which return owner.values return owner.values}').replace('let values=take()', 'let first=take(true) if first.length not=?1 return 0\n let values=take(false)')
AGGREGATE = '''Item:type=[n:int64 words:array<string>]
Pack:type=[values:array<Item> other:array<string>]
take=():>array<Item>=>{let owner=Pack[[Item[2 ['kept']]] ['released']] return owner.values}
exercise=():>int64=>{let values=take() values.push(Item[40 ['new']]) return if values.length=?2 values[0].n+values[1].n else 0}
main=():>int64=>{if exercise() not=?42 return 1
let before:int64=_arena_live_bytes
loop i in [0..50) {if exercise() not=?42 return 2}
return if _arena_live_bytes=?before 42 else 3}
'''
HOOK = '''let dropped:int64=0
Pack=type of [values:array<int64>
$__drop__
release=():>void=>{dropped+=values.length as int64}
]
take=(input:array<int64>):>array<int64>=>{let owner=Pack[input] return owner.values}
main=():>int64=>{let values=take([2]) values.push(40) return if dropped=?1 and values.length=?2 values[0]+values[1] else 0}
'''
CASES = [LOCAL, RETURN, NESTED, STORE, SHARED, SHARED_RECORD, CONST_RECORD, CALL, BRANCH, AGGREGATE]
COPIES = [LIVE, VIEW, LOOP, HOOK]

@pytest.mark.parametrize('source', CASES)
def test_array_field_transfers(tmp_path, source):
 execute(tmp_path, 'field-transfer', codegen(SrcFile(None, '$explicit_copies\n'+source), debug_locations=False))

@pytest.mark.parametrize('source', COPIES)
def test_array_field_retained_owner(tmp_path, source):
 execute(tmp_path, 'field-copy', codegen(SrcFile(None, source), debug_locations=False))
 with pytest.raises(ReportException, match='unproven copy'):
  codegen(SrcFile(None, '$explicit_copies\n'+source), debug_locations=False)


def test_native_array_field_transfers(tmp_path):
 from test_bootstrap_structural_text import build_program_driver, check_structural_text
 check_structural_text(build_program_driver(tmp_path), tmp_path,
  cases=['$explicit_copies\n'+s for s in CASES]+COPIES,
  errors=['$explicit_copies\n'+s for s in COPIES])


def test_array_field_allocation_positive_control(tmp_path, monkeypatch):
 from dewy.backend.udewy.lower import _Lowerer
 from dewy.semantic import hir
 compute = _Lowerer._compute_moves
 def without_fields(self, literal):
  fields = {id(node) for node in hir.walk(literal.body) if isinstance(node, hir.MemberAccess)}
  return compute(self, literal) - fields
 monkeypatch.setattr(_Lowerer, '_compute_moves', without_fields)
 execute(tmp_path, 'field-copy-control', codegen(SrcFile(None, LOCAL), debug_locations=False), expected=1)


def test_array_field_promotion_stays_in_the_inventory():
 from dewy.backend.udewy import lower
 codegen(SrcFile(None, '$explicit_copies\n'+AGGREGATE), debug_locations=False)
 notes = [note for note in lower.last_copy_notes if note.site == 'promoted from a record field']
 assert notes and all(note.kind == 'array' and note.policy_exempt for note in notes)
 assert all('frame-backed branch' in note.message for note in notes)
