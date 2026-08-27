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


def test_position_only_parameter_keeps_its_local_name() -> None:
    declarations = _declarations("""
let increment = (<value:int64>):>int64 => value + 1
let result = increment(41)
""")

    function = declarations['increment']
    assert isinstance(function, hir.FunctionLiteral)
    assert function.pos_or_kw_args[0].name == 'value'
    assert function.pos_or_kw_args[0].position_only
    assert isinstance(function.type, ty.FunctionType)
    assert function.type.pos_or_kw == [ty.PosOrKwArg(None, 'int64')]

    call = declarations['result']
    assert isinstance(call, hir.FunctionCall)
    assert len(call.pos_args) == 1


def test_position_only_parameter_cannot_be_called_by_name() -> None:
    with pytest.raises(UserError, match='unknown keyword argument `value`'):
        _declarations("""
let increment = (<value:int64>):>int64 => value + 1
let result = increment(value=41)
""")


def test_position_only_default_is_a_per_call_fallback() -> None:
    declarations = _declarations("""
let increment = (<value:int64=41>):>int64 => value + 1
let defaulted = increment()
let supplied = increment(40)
""")

    function = declarations['increment']
    assert isinstance(function, hir.FunctionLiteral)
    default = function.pos_or_kw_args[0]
    assert isinstance(default, hir.BoundParam)
    assert default.position_only
    assert isinstance(function.type, ty.FunctionType)
    assert function.type.pos_or_kw == [ty.PosOrKwArg(None, 'int64', required=False)]


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
    assert len(function.pos_or_kw_args) == 2
    assert function.kw_only_args == []
    default = function.pos_or_kw_args[1]
    assert isinstance(default, hir.BoundParam)
    assert default.type == 'int64'

    call = declarations['result']
    assert isinstance(call, hir.FunctionCall)
    assert call.kw_args == {}


def test_default_parameter_can_be_overridden_by_position_or_name() -> None:
    declarations = _declarations('''
let add = (x:int64 y=2):>int64 => x + y
let named = add(40 y=2)
let positional = add(40 2)
''')

    named = declarations['named']
    assert isinstance(named, hir.FunctionCall)
    assert list(named.kw_args) == ['y']

    positional = declarations['positional']
    assert isinstance(positional, hir.FunctionCall)
    assert len(positional.pos_args) == 2


def test_interleaved_default_keeps_its_positional_slot() -> None:
    declarations = _declarations('''
let combine = (left:int64 scale:int64=2 right:int64):>int64 => left + right * scale
let positional = combine(10 2 16)
let defaulted = combine(10 right=16)
''')

    function = declarations['combine']
    assert isinstance(function, hir.FunctionLiteral)
    assert [param.name for param in function.pos_or_kw_args] == ['left', 'scale', 'right']
    assert function.kw_only_args == []

    positional = declarations['positional']
    assert isinstance(positional, hir.FunctionCall)
    assert len(positional.pos_args) == 3

    defaulted = declarations['defaulted']
    assert isinstance(defaulted, hir.FunctionCall)
    assert len(defaulted.pos_args) == 1
    assert list(defaulted.kw_args) == ['right']


def test_named_binding_removes_a_parameter_from_the_remaining_positional_sequence() -> None:
    declarations = _declarations('''
let combine = (left:int64 scale:int64=2 right:int64):>int64 => left + right * scale
let result = combine(scale=2 10 16)
''')

    call = declarations['result']
    assert isinstance(call, hir.FunctionCall)
    assert len(call.pos_args) == 3
    assert call.kw_args == {}


def test_omitted_interleaved_default_does_not_skip_a_missing_required_parameter() -> None:
    with pytest.raises(UserError, match='no matching method'):
        _declarations('''
let combine = (left:int64 scale:int64=2 right:int64):>int64 => left + right * scale
let result = combine(10 16)
''')


def test_named_argument_selects_overload() -> None:
    declarations = _declarations("""
let integer = (value:int64):>int64 => value
let boolean = (value:bool):>bool => value
let overloaded = @integer & @boolean
let result = overloaded(value=true)
""")

    call = declarations['result']
    assert isinstance(call, hir.FunctionCall)
    assert call.type == 'bool'
    assert call.selected_method_index == 1
