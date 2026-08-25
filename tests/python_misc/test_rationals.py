import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError, UserError


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def _rational_type() -> ty.Type:
    declared = _declared('let r = 1/3')
    return declared['r'].expr.type


def test_integer_division_infers_a_rational() -> None:
    declared = _declared('let a = 1/3\nlet b:rational = a')
    assert isinstance(declared['a'].expr.type, ty.ObjectType)
    assert [f.name for f in declared['a'].expr.type.fields] == ['numerator', 'denominator']
    assert declared['b'].expr.type == declared['a'].expr.type


def test_literal_division_normalizes_at_compile_time() -> None:
    declared = _declared('let a = 6/(-8)')
    call = declared['a'].expr
    assert isinstance(call, hir.FunctionCall)
    assert [arg.value for arg in call.pos_args] == [-3, 4]


def test_decimal_literal_is_an_exact_rational() -> None:
    declared = _declared('let a = 9.8\nlet b = 1.25e2\nlet c = 5e-1')
    assert [arg.value for arg in declared['a'].expr.pos_args] == [49, 5]
    assert [arg.value for arg in declared['b'].expr.pos_args] == [125, 1]
    assert [arg.value for arg in declared['c'].expr.pos_args] == [1, 2]


def test_integers_promote_in_mixed_arithmetic_and_comparisons() -> None:
    declared = _declared('let a = 1/3\nlet b = a + 2\nlet c = 2 * a\nlet d = a <? 1\nlet e = -a')
    rational = declared['a'].expr.type
    assert declared['b'].expr.type == rational
    assert declared['c'].expr.type == rational
    assert declared['d'].expr.type == 'bool'
    assert declared['e'].expr.type == rational
    assert declared['b'].expr.func.name.endswith('_rational_add')
    assert declared['e'].expr.func.name.endswith('_rational_neg')


def test_literal_zero_divisor_is_rejected() -> None:
    with pytest.raises(TypeCheckError, match='division by zero'):
        _declared('let a = 1/0')


def test_true_division_needs_numbers() -> None:
    with pytest.raises(TypeCheckError, match='no matching overload for operator `/`'):
        _declared('let a = "x" / 2')


def test_rationals_need_the_prelude() -> None:
    with pytest.raises(UserError, match='rationals need the prelude'):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude = true\nlet a = 1/3'))
