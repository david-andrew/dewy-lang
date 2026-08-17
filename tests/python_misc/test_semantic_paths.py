from src.reporting import SrcFile
from src.semantic import check, hir, ty


def _declarations(source: str) -> dict[str, hir.AST]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return {
        item.name: item.expr
        for item in root.items
        if isinstance(item, hir.Declare)
    }


def test_p_is_an_ordinary_literal_preserving_function() -> None:
    declarations = _declarations("""
let juxtaposed = p"one.dewy"
let called = p("two.dewy")
let keyword = p(path="three.dewy")
""")

    for name, value in (
        ('juxtaposed', 'one.dewy'),
        ('called', 'two.dewy'),
        ('keyword', 'three.dewy'),
    ):
        call = declarations[name]
        assert isinstance(call, hir.FunctionCall)
        assert isinstance(call.func, hir.ExpressedIdentifier)
        assert call.func.name.endswith('_p')
        assert call.func.binding_id is not None
        assert call.type == ty.PathLiteralType(value)


def test_dynamic_p_call_has_thin_path_object_type() -> None:
    declarations = _declarations("""
let make = (text:string):>Path => p(text)
""")

    function = declarations['make']
    assert isinstance(function, hir.FunctionLiteral)
    path_type = ty.ObjectType((ty.ObjectField('path', 'string'),))
    assert function.rettype == path_type
    call = function.body
    assert isinstance(call, hir.FunctionCall)
    assert call.type == path_type


def test_exact_path_is_a_subtype_of_future_structural_definition() -> None:
    structural = ty.ObjectType((ty.ObjectField('path', 'string'),))
    literal = ty.PathLiteralType('library/path.dewy')
    system = ty.TypeSystem()

    assert system.is_subtype(literal, structural)


def test_module_declaration_can_shadow_prelude_p() -> None:
    root = check.typecheck_and_resolve(SrcFile(None, """
let p = (path:string):>[path:string] => [path=path]
let result = p"local.dewy"
"""))
    assert isinstance(root, hir.Block)
    declarations = {
        item.name: item
        for item in root.items
        if isinstance(item, hir.Declare)
    }

    local_p = declarations['p']
    result = declarations['result'].expr
    assert isinstance(result, hir.FunctionCall)
    assert isinstance(result.func, hir.ExpressedIdentifier)
    assert result.func.binding_id == local_p.binding_id
    assert result.type == ty.PathLiteralType('local.dewy')
