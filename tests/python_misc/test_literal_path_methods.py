"""A refined path view retains the methods of its constructor's result."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty


@pytest.mark.parametrize('expression', [
    'make("abc").text',
    'let value=make("abc")\nvalue.text',
    'make(path="abc").text',
])
def test_literal_path_prepares_declaring_methods(expression):
    source = '''
let Custom:type=[path:string text=():>string=>path]
let make=(path:string):>Custom=>[path=path]
''' + expression
    module, context = check._typecheck_module(SrcFile(None, source))
    assert module.type == 'string'
    result = module.items[-1]
    assert isinstance(result, hir.FunctionCall)
    assert isinstance(result.func, hir.ExpressedIdentifier)
    assert result.func.binding_id in context.binding_registry.by_id
    receiver = check._unwrap_literal_value(result.pos_args[0])
    assert isinstance(receiver.type, ty.PathLiteralType)
