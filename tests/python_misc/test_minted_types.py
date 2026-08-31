"""`type of` mints nominal object types; `T?` is optional sugar in type positions."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, source))


def test_minted_types_are_distinct_despite_equal_structure() -> None:
    with pytest.raises(TypeCheckError, match='expected `B`, got `A`'):
        _check(
            'let A:type = type of [x:int64]\n'
            'let B:type = type of [x:int64]\n'
            'let a:A = [x=1]\n'
            'let b:B = a'
        )


def test_every_alias_spelling_mints_and_intersecting_any_adds_nothing() -> None:
    root = _check(
        'let A:type = type of any & [x:int64]\n'
        'B = type of [x:int64]\n'
        'let C = type of any\n'
        'let a:A = [x=1]'
    )
    declares = {item.name: item for item in root.items if isinstance(item, hir.Declare)}
    for name, fields in [('A', 1), ('B', 1), ('C', 0)]:
        value = declares[name].expr
        assert isinstance(value, hir.TypeValue) and isinstance(value.value, ty.ObjectType)
        assert ty.user_branded(value.value) and value.value.brand == name
        assert len(value.value.fields) == fields
    assert declares['a'].expr.type == declares['A'].expr.value   # the literal takes the brand


def test_only_errors_and_objects_can_be_minted() -> None:
    with pytest.raises(NotImplementedYet, match='mintable so far'):
        _check('let A:type = type of int64')


def test_intersected_objects_cannot_repeat_a_field() -> None:
    with pytest.raises(UserError, match='declares field `x` twice'):
        _check('let A:type = type of [x:int64] & [x:int64]')


def test_optional_sugar_desugars_to_a_union_in_type_positions() -> None:
    root = _check('let x:int64? = none\nf = (v:string?):>bool => v is? none')
    declare = root.items[0]
    assert isinstance(declare, hir.Declare)
    assert ty.optional_payload(declare.annotation) == 'int64'
    f = root.items[1]
    assert isinstance(f.expr, hir.FunctionLiteral)
    assert ty.optional_payload(f.expr.pos_or_kw_args[0].type) == 'string'


def test_question_mark_stays_out_of_value_positions() -> None:
    with pytest.raises(NotImplementedYet, match='Postfix expression'):
        _check('let y = 5\nlet z = y?')


def test_string_literals_materialize_as_strings_in_optional_slots() -> None:
    # a cast typed as the union would be misread as an already-built cell
    root = _check("f = (v:string|none):>bool => v is? string\nlet r = f('hey')")
    call = root.items[1].expr
    assert isinstance(call, hir.FunctionCall)
    (argument,) = call.pos_args
    assert isinstance(argument, hir.RepresentationCast) and argument.type == ty.StringType()
