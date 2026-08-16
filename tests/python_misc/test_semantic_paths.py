from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic import check, hir, ty


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
let keyword = p(text="three.dewy")
""")

    for name, value in (
        ('juxtaposed', 'one.dewy'),
        ('called', 'two.dewy'),
        ('keyword', 'three.dewy'),
    ):
        call = declarations[name]
        assert isinstance(call, hir.FunctionCall)
        assert isinstance(call.func, hir.ExpressedIdentifier)
        assert call.func.name == 'p'
        assert call.type == ty.PathLiteralType(value)


def test_dynamic_p_call_has_thin_path_object_type() -> None:
    declarations = _declarations("""
let make = (text:string):>Path => p(text)
""")

    function = declarations['make']
    assert isinstance(function, hir.FunctionLiteral)
    assert function.rettype == ty.PATH_TYPE
    call = function.body
    assert isinstance(call, hir.FunctionCall)
    assert call.type == ty.PATH_TYPE


def test_exact_path_is_a_subtype_of_future_structural_definition() -> None:
    structural = ty.ObjectType((ty.ObjectField('text', ty.StringType()),))
    literal = ty.PathLiteralType('library/path.dewy')
    system = ty.TypeSystem()

    assert system.is_subtype(literal, ty.PATH_TYPE)
    assert system.is_subtype(literal, structural)
    assert system.is_subtype(ty.PATH_TYPE, structural)
