"""A proved union field loan dispatches layout without copying its owner."""
from pathlib import Path

import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE='''$explicit_copies
Left=type of [items:array<int64>]
Right=type of [padding:int64 items:array<int64>]
Node:type=Left|Right
size=(items:array<int64>):>int64 & no_effects=>items.length+40
forward=(owner:Node):>int64 & no_effects=>size(owner.items)
work=(owner:Node):>int64=>{
 let before:int64=_arena_allocated_bytes
 loop i in [0..1000) {if forward(owner) not=?42 return 1}
 return if _arena_allocated_bytes=?before 42 else 2
}
main=():>int64=>{
 let left:Node=Left[[20 22]]
 let right:Node=Right[7 [20 22]]
 if work(left) not=?42 return 3
 return work(right)
}'''
CASES=[SOURCE,SOURCE.replace('size(owner.items)','size(items=owner.items)'),
 SOURCE.replace('Left=type of [items:', 'Base=type of any\nLeft=type of Base & [items:').replace('Right=type of [padding:', 'Right=type of Base & [padding:')]
# Writing during evaluation of a later argument must preserve the earlier
# by-value argument. Whole-owner writes invalidate the shared loan proof.
MUTATING='''Left=type of [items:array<int64>]
Right=type of [padding:int64 items:array<int64>]
Node:type=Left|Right
size=(items:array<int64> ignored:int64):>int64=>items.length+40
mutate=(@owner:Node):>int64=>{owner=Right[0 []] return 0}
main=():>int64=>{
 let owner:Node=Left[[20 22]]
 return size(owner.items mutate(@owner))
}'''
CASES.extend([MUTATING,
 '$explicit_copies\n'+MUTATING.replace('size(owner.items ', 'size(owner.items.copy() ')])
ERRORS=['$explicit_copies\n'+MUTATING,
 SOURCE.replace('forward=(owner:Node):>int64 & no_effects=>size(owner.items)',
 'forward=(owner:Node):>int64 & no_effects=>{let kept=owner.items return size(kept)}')]

@pytest.mark.parametrize('source',CASES)
def test_common_field_loan(tmp_path,source):
 execute(tmp_path,'common-field',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_common_field_keeps_value_boundaries(source):
 with pytest.raises(ReportException):
  codegen(SrcFile(None,source),debug_locations=False)


def test_native_common_field_loans(tmp_path):
 from test_bootstrap_structural_text import build_program_driver,check_structural_text
 check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)

ITERATING=SOURCE.replace('forward=(owner:Node):>int64 & no_effects=>size(owner.items)',
 'forward=(owner:Node):>int64=>{let result:int64=0 loop item in owner.items {result+=item} return result}')
ITERATOR_SNAPSHOT=MUTATING.replace('return size(owner.items mutate(@owner))',
 'let result:int64=0 loop item in owner.items {mutate(@owner); result+=item} return result')
CASES.extend([ITERATING,ITERATING.replace('loop item in owner.items', 'loop item in owner.items and i in [0..2)'),ITERATOR_SNAPSHOT])
ERRORS.append('$explicit_copies\n'+ITERATOR_SNAPSHOT)
