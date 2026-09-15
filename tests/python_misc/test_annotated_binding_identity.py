"""Keyword-less annotations still declare one binding with a store contract."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import TypeCheckError, UserError
from test_dict_rebuild_helpers import check_generated


def test_annotated_assignment_keeps_the_original_binding():
    root, _ = check._typecheck_module(SrcFile(None, 'x:uint8=1\nx=2\nx'))
    declaration, assignment, read = root.items
    assert isinstance(declaration, hir.Declare)
    assert isinstance(assignment, hir.Assign)
    assert isinstance(read, hir.ExpressedIdentifier)
    assert declaration.binding_id == assignment.target.binding_id == read.binding_id


@pytest.mark.parametrize('annotation,value', [('uint8', '300'), ('int64', '"text"'), ('int64<n => n >? 0>', '0')])
def test_annotated_reassignment_preserves_the_contract(annotation, value):
    with pytest.raises((TypeCheckError, UserError)):
        check.typecheck_and_resolve(SrcFile(None, f'x:{annotation}=1\nx={value}\n'))


def test_annotated_functions_and_global_assignment(tmp_path):
    source = '''Fn:type=(x:int64):>int64
identity:Fn=(x:int64):>int64=>x
count:uint8=1
let next=():>int64=>{count+=1 return count as int64}
count=40
let main=():>int64=>identity(next()+1)
'''
    check_generated(codegen(SrcFile(None, source), debug_locations=False), tmp_path / 'annotated.udewy')
