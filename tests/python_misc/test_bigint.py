import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def _bigint_type() -> ty.Type:
    return _declared('let b:bigint = 1')['b'].expr.type


def test_bigint_literals_and_widening() -> None:
    declared = _declared('let a:bigint = 1\nlet b:bigint = 123456789012345678901234567890\nlet n:int64 = 7 transmute int64\nlet c:bigint = n')
    big = _bigint_type()
    assert declared['a'].expr.type == big and declared['a'].expr.func.name.endswith('_bigint_from_limbs')
    limbs = declared['b'].expr.pos_args[1]
    assert isinstance(limbs, hir.ArrayLiteral) and len(limbs.items) == 4  # 97 bits -> 4 base-2^32 limbs
    assert declared['c'].expr.func.name.endswith('_bigint_from_int')


def test_bigint_arithmetic_routes_and_folds() -> None:
    declared = _declared('let a:bigint = 5\nlet b = a * 3\nlet c = 2 - a\nlet d = a <? 10\nlet e:bigint = 2^100 + 1\nlet f = a ^ 3')
    big = _bigint_type()
    assert declared['b'].expr.type == big and declared['b'].expr.func.name.endswith('_bigint_mul')
    assert declared['c'].expr.func.name.endswith('_bigint_sub')
    assert declared['d'].expr.type == 'bool'
    assert declared['e'].expr.func.name.endswith('_bigint_from_limbs')  # constants fold before widening
    assert declared['f'].expr.func.name.endswith('_bigint_pow')


def test_bigint_true_division_is_not_yet_supported() -> None:
    with pytest.raises(NotImplementedYet, match='exact division of big integers'):
        _declared('let a:bigint = 5\nlet b = a / 2')
