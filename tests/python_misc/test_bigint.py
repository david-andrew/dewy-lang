import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def _bigint_type() -> ty.Type:
    return _declared('let b:bigint = 1')['b'].annotation   # the declared `0 | [sign limbs]`


def test_bigint_literals_and_widening() -> None:
    declared = _declared('let a:bigint = 1\nlet b:bigint = 123456789012345678901234567890\nlet n:int64 = 7 transmute int64\nlet c:bigint = n\nlet z:bigint = 0')
    big = _bigint_type()
    # `bigint` is `0 | [sign limbs]`: a nonzero constant is the object, zero the literal
    assert isinstance(big, ty.TypeOr) and big.items[0] == ty.IntegerLiteralType(0)
    assert isinstance(declared['a'].expr, hir.ObjectLiteral) and declared['a'].expr.type == big.items[1]
    limbs = {f.name: f.value for f in declared['b'].expr.fields}['limbs']
    assert isinstance(limbs, hir.ArrayLiteral) and len(limbs.items) == 4  # 97 bits -> 4 base-2^32 limbs
    assert declared['c'].expr.func.name.endswith('_bigint_from_int')
    assert isinstance(declared['z'].expr, hir.Integer) and declared['z'].expr.value == 0


def test_bigint_arithmetic_routes_and_folds() -> None:
    declared = _declared('let a:bigint = 5\nlet b = a * 3\nlet c = 2 - a\nlet d = a <? 10\nlet e:bigint = 2^100 + 1\nlet f = a ^ 3')
    big = _bigint_type()
    assert declared['b'].expr.type == big and declared['b'].expr.func.name.endswith('_bigint_mul')
    assert declared['c'].expr.func.name.endswith('_bigint_sub')
    assert declared['d'].expr.type == 'bool'
    assert isinstance(declared['e'].expr, hir.ObjectLiteral)  # constants fold before widening
    assert declared['f'].expr.func.name.endswith('_bigint_pow')


def test_bigint_true_division_is_a_rational() -> None:
    # `big / x` is the abstract rational; a big divisor must be proven nonzero
    declared = _declared('let a:bigint = 5\nlet b = a / 2\nlet c = if a not=? 0 (a / a) else 0')
    assert declared['b'].expr.func.name.endswith('_bigrational_make')
    with pytest.raises(TypeCheckError, match='cannot prove the divisor is nonzero'):
        _declared('let a:bigint = 5\nlet b = 1 / a')
    with pytest.raises(TypeCheckError, match='cannot prove the divisor is nonzero'):
        _declared('let a:bigint = 5\nlet b = a // a')
