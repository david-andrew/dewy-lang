import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError
from dewy.semantic.hir_display import type_to_dewy


@pytest.mark.parametrize(
    ('value', 'target', 'accepted'),
    [
        (-129, 'int8', False),
        (-128, 'int8', True),
        (127, 'int8', True),
        (128, 'int8', False),
        (-1, 'uint8', False),
        (0, 'uint8', True),
        (255, 'uint8', True),
        (256, 'uint8', False),
    ],
)
def test_integer_literal_fixed_width_boundaries(
    value: int,
    target: ty.Primitive,
    accepted: bool,
) -> None:
    type_system = ty.TypeSystem()
    assert type_system.is_subtype(ty.IntegerLiteralType(value), target) is accepted


def test_integer_literal_inhabits_abstract_numeric_ancestors() -> None:
    type_system = ty.TypeSystem()
    literal = ty.IntegerLiteralType(10**100)

    assert type_system.is_subtype(literal, 'int')
    assert type_system.is_subtype(literal, 'rational')
    assert type_system.is_subtype(literal, 'number')


def test_integer_literal_type_displays_as_its_exact_value() -> None:
    assert type_to_dewy(ty.IntegerLiteralType(-42)) == '-42'


def test_generic_integer_literal_inference() -> None:
    type_system = ty.TypeSystem()
    method = ty.FunctionType(
        [ty.PosOrKwArg('left', 'T'), ty.PosOrKwArg('right', 'T')],
        [],
        None,
        'T',
        [ty.GenericParam('T', 'number')],
    )

    left_concrete = type_system.match_best_function(
        [method],
        ['int64', ty.IntegerLiteralType(2)],
    ).method
    right_concrete = type_system.match_best_function(
        [method],
        [ty.IntegerLiteralType(2), 'int64'],
    ).method
    literals = type_system.match_best_function(
        [method],
        [ty.IntegerLiteralType(40), ty.IntegerLiteralType(2)],
    ).method
    contextual = type_system.match_best_function(
        [method],
        [ty.IntegerLiteralType(40), ty.IntegerLiteralType(2)],
        expected_return='int64',
    ).method

    assert left_concrete.ret == 'int64'
    assert right_concrete.ret == 'int64'
    assert literals.ret == 'int'
    assert contextual.ret == 'int64'


def test_literal_matching_incomparable_overloads_is_ambiguous() -> None:
    type_system = ty.TypeSystem()
    methods = [
        ty.FunctionType([ty.PosOrKwArg('value', 'int8')], [], None, 'int8'),
        ty.FunctionType([ty.PosOrKwArg('value', 'uint8')], [], None, 'uint8'),
    ]

    with pytest.raises(ty.DispatchError, match='ambiguous'):
        type_system.match_best_function(methods, [ty.IntegerLiteralType(1)])


def _main_body(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    declaration = root.items[-1]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.FunctionLiteral)
    assert isinstance(declaration.expr.body, hir.Block)
    return declaration.expr.body


def test_fixed_width_context_propagates_through_operators_and_calls() -> None:
    body = _main_body("""
let add = (a:int64 b:int64):>int64 => {
    return a + b
}
let main = ():>int64 => {
    let x:int64 = 40
    let sum:int64 = x + 2
    let quotient:int64 = x // 2
    let shifted:int64 = x << 2
    let direct:int64 = add(40 2)
    let composite:int64 = add(20 + 20 2)
    let negative:int64 = -1
    return direct
}
""")
    expressions = {
        item.name: item.expr
        for item in body.items
        if isinstance(item, hir.Declare)
    }

    assert expressions['x'].type == ty.IntegerLiteralType(40)
    for name in ('sum', 'quotient', 'shifted', 'direct', 'composite'):
        assert expressions[name].type == 'int64'
    assert expressions['negative'].type == ty.IntegerLiteralType(-1)


@pytest.mark.parametrize(
    ('annotation', 'value'),
    [
        ('uint8', '-1'),
        ('int8', '128'),
    ],
)
def test_out_of_range_literal_initialization_is_rejected(
    annotation: str,
    value: str,
) -> None:
    source = f"""
let main = ():>int64 => {{
    let value:{annotation} = {value}
    return 0
}}
"""
    with pytest.raises(TypeCheckError, match='type mismatch'):
        check.typecheck_and_resolve(SrcFile(None, source))
