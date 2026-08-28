import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError
from dewy.semantic.hir_display import type_to_dewy


def _check(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, '$no_prelude = true\n' + source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_implicit_type_aliases_with_refinements() -> None:
    declared = _check('Positive = int< i=>i>?0 >\nNonEmptyArray = array< length>?0 >')
    positive = declared['Positive'].expr
    assert isinstance(positive, hir.TypeValue)
    assert positive.value == ty.RefinedType('int', (ty.Proposition('self', '>?', 0),))
    assert type_to_dewy(positive.value) == 'int<i => i >? 0>'
    non_empty = declared['NonEmptyArray'].expr.value
    assert non_empty == ty.RefinedType('array', (ty.Proposition('length', '>?', 0),))


def test_refined_annotations_prove_from_literals_and_keep_the_base_type() -> None:
    declared = _check(
        'Positive = int< i=>i>?0 >\nNonEmptyArray = array< length>?0 >\n'
        'score:Positive = 42\nvalues:NonEmptyArray<int> = [3 5 8]\nfirst = values[0]'
    )
    assert isinstance(declared['score'].annotation, ty.RefinedType)
    assert declared['score'].annotation.base == 'int'
    assert declared['score'].expr.type == ty.IntegerLiteralType(42)  # the proven literal
    values = declared['values']
    assert isinstance(values.annotation, ty.RefinedType)
    assert values.annotation.base == ty.ArrayType('int64', None)
    assert values.annotation.propositions == (ty.Proposition('length', '>?', 0),)
    assert declared['first'].expr.type == 'int64'


def test_refuted_refinement_is_an_error() -> None:
    with pytest.raises(TypeCheckError, match='refinement refuted'):
        _check('Positive = int< i=>i>?0 >\nscore:Positive = -3')
    with pytest.raises(TypeCheckError, match='refinement refuted'):
        _check('NonEmpty = array< length>?0 >\nlet values:NonEmpty<int64> = []')


def test_unprovable_refinement_is_reported_as_unknown() -> None:
    # the checker defers a runtime value to the bounds analysis, which reports
    # it as unproven (neither proven nor refuted) with what it knows
    from dewy.backend.udewy import codegen
    from dewy.semantic.errors import UserError

    with pytest.raises(UserError, match='cannot prove refinement') as info:
        codegen(SrcFile(None, 'Positive = int< i=>i>?0 >\nlet n:int64 = 5 transmute int64\nlet score:Positive = n\n'))
    assert 'neither proven nor refuted' in str(info.value)
    # a guard establishes the fact
    codegen(SrcFile(None, 'Positive = int64< i=>i>?0 >\nlet n:int64 = 5 transmute int64\nlet main = ():>int64 => { if n >? 0 { let score:Positive = n  return score }  return 0 }\n'))


def test_refinement_conditions_and_parameters_are_distinguished() -> None:
    declared = _check('Small = array< int64 length<=?4 >\nlet xs:Small = [1 2]')
    assert declared['xs'].annotation == ty.RefinedType(
        ty.ArrayType('int64', None), (ty.Proposition('length', '<=?', 4),)
    )
    with pytest.raises(TypeCheckError, match='refinement refuted'):
        _check('Small = array< int64 length<=?4 >\nlet xs:Small = [1 2 3 4 5]')


def test_refinement_subjects_must_apply() -> None:
    with pytest.raises(TypeCheckError, match='refinement subject does not apply'):
        _check('Odd = int< length>?0 >')
