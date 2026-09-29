"""Conditional common-field views retain every root and its value boundary."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile,ReportException
from test_scalar_projection import execute
from test_common_field_loans import SOURCE

SOURCE=SOURCE.replace('forward=(owner:Node):>int64 & no_effects=>size(owner.items)', '''forward=(owner:Node flag:bool):>int64 & no_effects=>{
 const first:array<int64>=if flag owner.items else [20 22]
 const selected:array<int64>=if flag first else [20 22]
 return size(selected)
}''').replace('forward(owner) not=?42','forward(owner true) not=?42 or forward(owner false) not=?42')
RETAINED='''Left=type of [items:array<int64>]
Right=type of [padding:int64 items:array<int64>]
Node:type=Left|Right
make=():>Node=>Left[[42]]
work=(flag:bool):>int64=>{
 let owner=make()
 const first:array<int64>=if flag owner.items else []
 const selected:array<int64>=if flag first else []
 let changed=owner
 if changed is? Left {changed.items.clear()}
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>work(true)'''
CASES=[SOURCE,RETAINED]
ERRORS=['$explicit_copies\n'+RETAINED,
 SOURCE.replace('return size(selected)','selected.clear()\n return size(selected)')]

@pytest.mark.parametrize('source',CASES)
def test_common_field_selection(tmp_path,source):
 execute(tmp_path,'common-selection',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_common_field_selection_retains_owners(source):
 with pytest.raises(ReportException):
  codegen(SrcFile(None,source),debug_locations=False)


def test_native_common_field_selections(tmp_path):
 from test_bootstrap_structural_text import build_program_driver,check_structural_text
 check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
