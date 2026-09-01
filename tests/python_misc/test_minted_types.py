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


def test_intersected_objects_may_narrow_but_not_weaken_a_field() -> None:
    _check('let A:type = type of [x:int64] & [x:int64]')   # a same-typed repeat replaces
    with pytest.raises(UserError, match='weakens field `x`'):
        _check('let A:type = type of [x:int8] & [x:int64]')


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


DESCENT = (
    'let Token = type of any & [kind:int64]\n'
    'let Whitespace = type of Token\n'
    'let Name = type of [text:string] & Token\n'
)


def test_a_minted_child_is_a_subtype_of_its_parent_with_the_parent_fields_leading() -> None:
    root = _check(DESCENT + 'describe = (t:Token):>int64 => t.kind\nlet r = describe(Name(text="a" kind=1))')
    declares = {item.name: item for item in root.items if isinstance(item, hir.Declare)}
    name = declares['Name'].expr.value
    token = declares['Token'].expr.value
    assert [field.name for field in name.fields] == ['kind', 'text']
    assert ty.user_brand_descends(name, token) and not ty.user_brand_descends(token, name)
    assert ty.USER_BRAND_PARENTS['Whitespace'] == 'Token'


def test_minted_siblings_stay_distinct() -> None:
    with pytest.raises(TypeCheckError, match='expected `Whitespace`, got `Name`'):
        _check(DESCENT + 'let w:Whitespace = Name(text="a" kind=1)')


def test_a_minted_type_has_at_most_one_nominal_parent() -> None:
    with pytest.raises(NotImplementedYet, match='two nominal parents'):
        _check(DESCENT + 'let Both = type of Whitespace & Name')


def test_an_empty_minted_type_names_its_single_inhabitant_in_value_positions() -> None:
    unit = 'let Blank = type of any\nlet Space = type of Blank\n'
    root = _check(unit + 'let w = Space\nlet s:Space = Space\nlet k:Space = Space()\nlet b:Blank = Space')
    declares = {item.name: item for item in root.items if isinstance(item, hir.Declare)}
    space = declares['Space'].expr.value
    for name in ('w', 's', 'k', 'b'):
        assert isinstance(declares[name].expr, hir.ObjectLiteral) and declares[name].expr.type == space
    with pytest.raises(TypeCheckError, match='expected `Name`'):
        _check(DESCENT + unit + 'let n:Name = Space')   # the inhabitant must fit the expectation
    with pytest.raises(NotImplementedYet, match='runtime type values'):
        _check(DESCENT + 'let w = Whitespace')          # not empty: it carries `kind`, so it is only a type here
