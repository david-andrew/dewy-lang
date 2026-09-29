"""Read-only array equality ignores length refinements, retaining representation."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    "main=():>int64=>{let xs:array<string>=['a' 'b'] return if xs =? ['a' 'b'] 42 else 1}",
    "main=():>int64=>{let xs:array<string>=['a' 'b'] return if ['a' 'b'] =? xs 42 else 1}",
    "main=():>int64=>{let xs:array<string>=['aa'] return if xs not=? ['a'] 42 else 1}",
    "Box:type=[items:array<string>]\nmain=():>int64=>{let box=Box[['a' 'b']] return if box.items =? ['a' 'b'] 42 else 1}",
    "main=():>int64=>{let xs:array<array<string>>=[['a']] return if xs =? [['a']] and xs not=? [['a' 'b']] 42 else 1}",
    "main=():>int64=>{let xs:array<int64<v=>v>=?0>>=[1 2] return if xs =? [1 2] 42 else 1}",
]
ERRORS = [
    "main=():>bool=>{let a:array<uint8>=[1] let b:array<uint64>=[1] return a =? b}",
    "A=type of [value:int64]\nB=type of [value:int64]\nmain=():>bool=>{let a:array<A>=[A[1]] let b:array<B>=[B[1]] return a =? b}",
]

@pytest.mark.parametrize('source', CASES)
def test_array_equality_with_element_facts(tmp_path, source):
    execute(tmp_path, 'array-equality-elements', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_array_equality_does_not_reinterpret_elements(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_array_equality_element_shapes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
