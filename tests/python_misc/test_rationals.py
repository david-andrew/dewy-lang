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


def _big(node: hir.AST) -> int:
    """The value a big-integer constant carries: the literal `0`, or the `[sign limbs]` object."""
    if isinstance(node, hir.Integer):
        assert node.value == 0
        return 0
    assert isinstance(node, hir.ObjectLiteral), node
    fields = {field.name: field.value for field in node.fields}
    value = sum(limb.value << (32 * i) for i, limb in enumerate(fields['limbs'].items))
    return fields['sign'].value * value


def _parts(node: hir.AST) -> tuple[int, int]:
    """The (numerator, denominator) a materialized rational constant carries.

    The abstract `rational` materializes as `_bigrational_coprime(<big> <big>)`
    (or the literal `0`); the explicit `rational<int64>` as `_rational_make(n d)`.
    """
    if isinstance(node, hir.Integer):
        assert node.value == 0
        return (0, 1)
    assert isinstance(node, hir.FunctionCall)
    if node.func.name.endswith('_rational_make'):
        return tuple(arg.value for arg in node.pos_args)
    assert node.func.name.endswith('_bigrational_coprime'), node.func.name
    return tuple(_big(arg) for arg in node.pos_args)


def _nonzero_fields(type_: ty.Type) -> list[str]:
    """The field names of a `0 | [...]` type's nonzero object."""
    assert isinstance(type_, ty.TypeOr) and type_.items[0] == ty.IntegerLiteralType(0)
    nonzero = type_.items[1]
    assert isinstance(nonzero, ty.ObjectType)
    return [f.name for f in nonzero.fields]


def test_integer_division_infers_a_rational() -> None:
    declared = _declared('let a = 1/3\nlet b:rational = a\nlet w:rational<int64> = 1/3')
    # the abstract rational is `0 | [numerator denominator]` over big parts
    assert _nonzero_fields(declared['a'].expr.type) == ['numerator', 'denominator']
    assert declared['b'].expr.type == declared['a'].expr.type
    assert [f.name for f in declared['w'].expr.type.fields] == ['numerator', 'denominator']  # the explicit word form


def test_literal_division_normalizes_at_compile_time() -> None:
    declared = _declared('let a = 6/(-8)')
    assert _parts(declared['a'].expr) == (-3, 4)


def test_decimal_literal_is_an_exact_rational() -> None:
    declared = _declared('let a = 9.8\nlet b = 1.25e2\nlet c = 5e-1')
    assert _parts(declared['a'].expr) == (49, 5)
    assert _parts(declared['b'].expr) == (125, 1)
    assert _parts(declared['c'].expr) == (1, 2)


def test_integers_promote_in_mixed_arithmetic_and_comparisons() -> None:
    declared = _declared('let a = 1/3\nlet b = a + 2\nlet c = 2 * a\nlet d = a <? 1\nlet e = -a')
    rational = declared['a'].expr.type
    # the abstract rational's arithmetic is total (big-integer parts): no error member
    assert declared['b'].expr.type == rational
    assert declared['c'].expr.type == rational
    assert declared['d'].expr.type == 'bool'
    assert declared['e'].expr.type == rational
    assert declared['b'].expr.func.name.endswith('_bigrational_add')
    assert declared['e'].expr.func.name.endswith('_bigrational_neg')
    # the explicit `rational<int64>` keeps word parts and the `| Overflow` result
    word = _declared('let a:rational<int64> = 1/3\nlet b = a + 2\nlet d = a <? 1')
    assert word['b'].expr.func.name.endswith('_rational_add')
    assert word['b'].expr.type == ty.union(word['a'].expr.type, 'Overflow')
    assert word['d'].expr.type == 'bool'


def test_literal_zero_divisor_is_rejected() -> None:
    with pytest.raises(TypeCheckError, match='division by zero'):
        _declared('let a = 1/0')


def test_true_division_needs_numbers() -> None:
    with pytest.raises(TypeCheckError, match='no matching overload for operator `/`'):
        _declared('let a = "x" / 2')


def test_rationals_need_the_prelude() -> None:
    with pytest.raises(UserError, match='need the prelude'):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude = true\nlet a = 1/3'))


def test_constant_integer_powers_fold() -> None:
    declared = _declared('let a = 2^10\nlet b = (-3)^3')
    assert isinstance(declared['a'].expr, hir.Integer) and declared['a'].expr.value == 1024
    assert isinstance(declared['b'].expr, hir.Integer) and declared['b'].expr.value == -27


def test_negative_constant_exponent_makes_a_rational() -> None:
    declared = _declared('let a = 2^(-3)\nlet b = (2/3)^(-2)')
    assert _parts(declared['a'].expr) == (1, 8)
    # constant rational bases fold too; the `let` materializes the result
    assert _parts(declared['b'].expr) == (9, 4)
    assert declared['b'].expr.type == _rational_type()


def test_constant_rational_expressions_fold_at_compile_time() -> None:
    declared = _declared('const a = 1/3 + 1/6\nconst b = a * 4\nlet c = b')
    assert isinstance(declared['a'].expr, hir.RationalConstant)
    assert (declared['a'].expr.numerator, declared['a'].expr.denominator) == (1, 2)
    assert isinstance(declared['b'].expr, hir.RationalConstant)
    assert (declared['b'].expr.numerator, declared['b'].expr.denominator) == (2, 1)
    assert declared['b'].expr.type == ty.RationalLiteralType(2, 1)
    # a `let` of a constant materializes the folded value, not a chain of calls
    assert _parts(declared['c'].expr) == (2, 1)


def test_unit_scales_fold_into_dimensioned_constants() -> None:
    declared = _declared('import units\nconst speed = 30m/s\nconst accel = 9.8(m/s^2)\nlet energy = 1/2 * 10kg * speed^2')
    speed = declared['speed'].expr
    assert isinstance(speed.type, ty.QuantityType)
    assert speed.type.dimension == ty.dimension(('Length', 1), ('Time', -1))
    assert speed.type.number == ty.IntegerLiteralType(30)  # metres per second
    assert declared['accel'].expr.type.dimension == ty.dimension(('Length', 1), ('Time', -2))
    assert declared['accel'].expr.type.number == ty.RationalLiteralType(49, 5)
    energy = declared['energy'].expr
    assert isinstance(energy.type, ty.QuantityType)
    assert energy.type.dimension == ty.dimension(('Mass', 1), ('Length', 2), ('Time', -2))
    # whole-valued results stay integer quantities (a runtime `int` after `let` widening)
    assert isinstance(energy, hir.Integer) and energy.value == 4500
    assert energy.type.number == 'int'


def test_mismatched_dimensions_are_rejected() -> None:
    with pytest.raises(TypeCheckError, match='incompatible physical dimensions'):
        _declared('import units\nlet x = 2kg + 3m')
    with pytest.raises(TypeCheckError, match='incompatible physical dimensions'):
        _declared('import units\nlet x = 2kg <? 3m')


def test_derived_units_are_exact_compile_time_scales() -> None:
    declared = _declared('import units\nconst newton = N\nconst joule = J')
    assert declared['newton'].expr.type.dimension == ty.dimension(('Mass', 1), ('Length', 1), ('Time', -2))
    assert declared['newton'].expr.type.number == ty.IntegerLiteralType(1)  # SI-canonical scales
    assert declared['joule'].expr.type.number == ty.IntegerLiteralType(1)
    assert declared['joule'].expr.type.dimension == ty.dimension(('Mass', 1), ('Length', 2), ('Time', -2))


def test_runtime_integer_power_routes_to_the_prelude() -> None:
    declared = _declared('let n:int64 = 3\nlet e:uint8 = 2\nlet a = n^2\nlet b = n^e')
    assert declared['a'].expr.func.name.endswith('_int_pow')
    assert declared['b'].expr.func.name.endswith('_int_pow')
    assert declared['a'].expr.type == 'int64'


def test_runtime_signed_exponent_is_rejected() -> None:
    with pytest.raises(TypeCheckError, match='known to be non-negative'):
        _declared('let n:int64 = 3\nlet e:int64 = 2\nlet a = n^e')


def test_power_base_must_be_numeric() -> None:
    with pytest.raises(TypeCheckError, match='no matching overload for operator `\\^`'):
        _declared('let a = "x"^2')
    with pytest.raises(TypeCheckError, match='exponent must be an integer'):
        _declared('let a = 2^(1/2)')


def _fixed_type() -> ty.Type:
    return _declared('let f:fixed = 1/2')['f'].expr.type


def test_fixed_constants_round_to_nearest_raw() -> None:
    declared = _declared('let a:fixed = 1/3\nlet b:fixed = 1.25\nlet c:fixed = -7')

    def raw(name: str) -> int:
        literal = declared[name].expr  # a `[raw = …]` literal: the constant raw is a compile-time fact
        return next(f.value.value for f in literal.fields if f.name == 'raw')

    assert raw('a') == 1431655765
    assert raw('b') == 5368709120
    assert raw('c') == -30064771072


def test_fixed_absorbs_integers_and_rationals() -> None:
    declared = _declared('let f:fixed = 1/2\nlet a = f + 1\nlet b = 2/3 * f\nlet c = f <? 1/3\nlet d = -f')
    fixed = _fixed_type()
    assert declared['a'].expr.type == fixed and declared['a'].expr.func.name.endswith('_fixed_add')
    assert declared['b'].expr.type == fixed and declared['b'].expr.func.name.endswith('_fixed_mul')
    assert declared['c'].expr.type == 'bool'
    assert declared['d'].expr.type == fixed


def test_trig_takes_exact_degree_constants_and_fixed_angles() -> None:
    declared = _declared('import units\nlet a = cos(45°)\nlet r:fixed = 1/2\nlet b = sin(r * rad)\nlet w = 20N * 10m * cos(45°)')
    fixed = _fixed_type()
    assert declared['a'].expr.type == fixed
    assert declared['b'].expr.type == fixed
    work = declared['w'].expr.type
    assert isinstance(work, ty.QuantityType) and work.number == fixed
    assert work.dimension == ty.dimension(('Mass', 1), ('Length', 2), ('Time', -2))


def test_time_is_canonical_in_seconds() -> None:
    declared = _declared('const a = 300ms\nconst b = 2minute\nconst c = 1ns')
    assert declared['a'].expr.type.number == ty.RationalLiteralType(3, 10)
    assert declared['b'].expr.type.number == ty.IntegerLiteralType(120)
    assert declared['c'].expr.type.number == ty.RationalLiteralType(1, 10**9)
