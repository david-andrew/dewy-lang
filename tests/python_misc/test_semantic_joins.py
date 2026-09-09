"""Semantic joins preserve a covering type and a stable union member order."""

import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty


def test_join_absorbs_subtypes_without_promoting_unrelated_members() -> None:
    system = ty.TypeSystem()
    assert system.join() == ty.BOTTOM_TYPE
    assert system.join('int64', ty.union('string', 'int')) == ty.union('string', 'int')
    assert system.join('int', 'string', 'int64') == ty.union('int', 'string')
    assert system.join('int8', 'int64') == ty.union('int8', 'int64')
    assert system.join('int64', 'any') == 'any'
    positive = ty.RefinedType('int64', (ty.Proposition('self', '>?', 0),))
    assert system.join(positive, 'int64') == 'int64'
    assert system.join('int64', positive) == 'int64'
    negative = ty.RefinedType('int64', (ty.Proposition('self', '<?', 0),))
    assert system.join(positive, negative) == ty.union(positive, negative)


def test_join_keeps_one_representative_of_equivalent_types() -> None:
    alias = ty.NamedType('Alias', 1)
    alias.resolve('int64')
    system = ty.TypeSystem()
    assert alias != 'int64'
    assert system.is_subtype(alias, 'int64') and system.is_subtype('int64', alias)
    assert system.join(alias, 'int64') is alias
    assert system.join('int64', alias) == 'int64'


@pytest.mark.parametrize('first, second', [('parent', 'child'), ('child', 'parent')])
def test_inferred_returns_join_a_child_into_its_family(first: str, second: str) -> None:
    root = check.typecheck_and_resolve(SrcFile(None, f'''
T = $abstract type of any & [n:int64]
A = type of T
let choose = (flag:bool parent:T child:A) => {{
    if flag return {first}
    return {second}
}}
'''))
    declarations = {item.name: item for item in root.items if isinstance(item, hir.Declare)}
    assert declarations['choose'].expr.rettype == declarations['T'].expr.value
