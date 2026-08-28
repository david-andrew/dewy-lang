"""`d:int64<d not=? 0>` (the declared name is the value) and `int64 & ~0` (structural exclusion)."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, '$no_prelude = true\n' + source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def _param_types(declared: dict[str, hir.Declare], name: str) -> list[ty.Type]:
    function = declared[name].expr
    assert isinstance(function, hir.FunctionLiteral)
    return [param.type for param in function.pos_or_kw_args]


def test_declared_name_is_the_refinement_subject() -> None:
    declared = _declared(
        'let f = (d:int64<d not=? 0> xs:array<int64 xs.length >? 0> ys:array<int64 length>?1>):>int64 => 0\n'
        'let g = (n:int64<n >? 0 and n <? 10>):>int64 => n\n'
    )
    d, xs, ys = _param_types(declared, 'f')
    assert d == ty.RefinedType('int64', (ty.Proposition('self', 'not=?', 0),))
    assert xs == ty.RefinedType(ty.ArrayType('int64', None), (ty.Proposition('length', '>?', 0),))
    assert ys == ty.RefinedType(ty.ArrayType('int64', None), (ty.Proposition('length', '>?', 1),))
    (n,) = _param_types(declared, 'g')
    assert n == ty.RefinedType('int64', (ty.Proposition('self', '>?', 0), ty.Proposition('self', '<?', 10)))
    # bindings and fields get the same treatment; aliases keep the lambda form
    declared = _declared('let v:int64<v >=? 0> = 3\nlet T:type = [count:int64<count >? 0>]\nPositive = int64<i => i >? 0>\n')
    assert declared['v'].annotation == ty.RefinedType('int64', (ty.Proposition('self', '>=?', 0),))
    with pytest.raises(TypeCheckError, match='has no field `Positive`'):
        _declared('Positive = int64<Positive >? 0>\n')  # no value name in an alias: read as a field


def test_intersection_with_negated_literals_is_a_not_equal_refinement() -> None:
    declared = _declared('let f = (d:int64 & ~0 e:~(0 | 1) & int64 s:int64 & ~0 & ~1):>int64 => 0\n')
    d, e, s = _param_types(declared, 'f')
    assert d == ty.RefinedType('int64', (ty.Proposition('self', 'not=?', 0),))
    assert e == ty.RefinedType('int64', (ty.Proposition('self', 'not=?', 0), ty.Proposition('self', 'not=?', 1)))
    assert s == ty.RefinedType('int64', (ty.Proposition('self', 'not=?', 0), ty.Proposition('self', 'not=?', 1)))
    # a negation of a non-literal stays an ordinary intersection type
    declared = _declared('let T:type = [a:int64]\nlet U:type = [b:int64]\nlet f = (x:T & ~U):>int64 => 0\n')
    (x,) = _param_types(declared, 'f')
    assert isinstance(x, ty.TypeAnd)


def test_literal_and_exclusion_partition_an_overload_set() -> None:
    source = (
        'let DivZero:type = type of error\n'
        'let safe_div = ((n:int64 d:0):>DivZero => DivZero) & ((n:int64 d:int64 & ~0):>int64 => n // d)\n'
        'let main = ():>int64 => { let d:int64 = 4 transmute int64  let a = safe_div(6 0)  let b = safe_div(6 3)  if d not=? 0 { return safe_div(20 d) }  return 0 }\n'
    )
    declared = _declared(source)
    body = declared['main'].expr.body
    calls = [item.expr for item in body.items if isinstance(item, hir.Declare) and item.name in ('a', 'b')]
    assert [call.selected_method_index for call in calls] == [0, 1]
    codegen(SrcFile(None, source))
    with pytest.raises(UserError, match='cannot prove refinement'):
        codegen(SrcFile(None, source.replace('if d not=? 0 { return safe_div(20 d) }', 'return safe_div(20 d)')))


def test_field_subjects_refine_object_values() -> None:
    ratio = 'let Ratio:type = [top:int64 bottom:int64]\n'
    declared = _declared(ratio + 'let f = (a:Ratio<bottom >? 0> b:Ratio<b.bottom not=? 0> c:Ratio<q => q.bottom >=? 1>):>int64 => 0\n')
    a, b, c = _param_types(declared, 'f')
    assert a.propositions == (ty.Proposition('.bottom', '>?', 0),)
    assert b.propositions == (ty.Proposition('.bottom', 'not=?', 0),)
    assert c.propositions == (ty.Proposition('.bottom', '>=?', 1),)
    value = ratio + 'let value = (r:Ratio<bottom >? 0>):>int64 => r.top // r.bottom\n'   # the field fact proves the division
    codegen(SrcFile(None, value + 'let main = ():>int64 => { let half:Ratio = [top=1 bottom=2]  return value([top=20 bottom=2]) + value(half) }\n'))
    codegen(SrcFile(None, value + 'let f = (r:Ratio):>int64 => { if r.bottom >? 0 { return value(r) }  return 0 }\n'))
    with pytest.raises(UserError, match='refinement refuted'):
        codegen(SrcFile(None, value + 'let a = value([top=1 bottom=0])\n'))
    with pytest.raises(UserError, match='cannot prove refinement') as info:
        codegen(SrcFile(None, value + 'let f = (r:Ratio):>int64 => value(r)\n'))
    assert '`r.bottom` has no known bound' in str(info.value)
    with pytest.raises(UserError, match='refinement refuted') as info:  # the assigned field is exactly 0
        codegen(SrcFile(None, value + 'let f = (r:Ratio):>int64 => { if r.bottom >? 0 { r.bottom = 0  return value(r) }  return 0 }\n'))
    assert '`r.bottom` is 0' in str(info.value)
    with pytest.raises(UserError, match='cannot prove refinement'):  # a reassigned root forgets the guard
        codegen(SrcFile(None, value + 'let f = (r:Ratio s:Ratio):>int64 => { if r.bottom >? 0 { r = s  return value(r) }  return 0 }\n'))
    with pytest.raises(TypeCheckError, match='has no field `width`'):
        _declared(ratio + 'let f = (r:Ratio<width >? 0>):>int64 => 0\n')
