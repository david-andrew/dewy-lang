import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import UserError


def _declarations(source: str) -> dict[str, hir.AST]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return {
        item.name: item.expr
        for item in root.items
        if isinstance(item, hir.Declare)
    }


def test_named_arguments_can_be_reordered() -> None:
    declarations = _declarations("""
let subtract = (x:int64 y:int64):>int64 => x - y
let result = subtract(y=2 x=5)
""")

    call = declarations['result']
    assert isinstance(call, hir.FunctionCall)
    assert call.pos_args == []
    assert list(call.kw_args) == ['y', 'x']
    assert all(
        ty.TypeSystem().is_subtype(argument.type, 'int64')
        for argument in call.kw_args.values()
    )


@pytest.mark.parametrize(
    ('arguments', 'message'),
    [
        ('unknown=1', 'unknown keyword argument `unknown`'),
        ('x=1 x=2', 'duplicate keyword argument `x`'),
    ],
)
def test_invalid_keyword_arguments_have_specific_diagnostics(
    arguments: str,
    message: str,
) -> None:
    source = f"""
let identity = (x:int64):>int64 => x
let result = identity({arguments})
"""
    with pytest.raises(UserError, match=message):
        check.typecheck_and_resolve(SrcFile(None, source))


def test_default_parameter_type_is_inferred_and_may_be_omitted() -> None:
    declarations = _declarations("""
let add = (x:int64 y=2):>int64 => x + y
let result = add(40)
""")

    function = declarations['add']
    assert isinstance(function, hir.FunctionLiteral)
    assert len(function.kw_only_args) == 1
    default = function.kw_only_args[0]
    assert isinstance(default, hir.BoundParam)
    assert default.type == ty.IntegerLiteralType(2)

    call = declarations['result']
    assert isinstance(call, hir.FunctionCall)
    assert call.kw_args == {}


def test_named_argument_selects_overload() -> None:
    declarations = _declarations("""
let integer = (value:int64):>int64 => value
let boolean = (value:bool):>bool => value
let overloaded = integer & boolean
let result = overloaded(value=true)
""")

    call = declarations['result']
    assert isinstance(call, hir.FunctionCall)
    assert call.type == 'bool'
    assert call.selected_method_index == 1
