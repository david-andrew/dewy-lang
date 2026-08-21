import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import UserError


def test_standalone_type_block_produces_compile_time_value() -> None:
    root = check.typecheck_and_resolve(SrcFile(None, '<int64 | string>'))

    assert isinstance(root, hir.Block)
    value = root.items[0]
    assert isinstance(value, hir.TypeValue)
    assert value.type == ty.TYPE_TYPE
    assert value.value == ty.TypeOr(['int64', 'string'])


def test_unannotated_type_value_declaration_defines_alias() -> None:
    root = check.typecheck_and_resolve(SrcFile(None, '''
const Index = <int64>
let value:Index = 42
'''))

    assert isinstance(root, hir.Block)
    alias = root.items[0]
    value = root.items[1]
    assert isinstance(alias, hir.Declare)
    assert isinstance(alias.expr, hir.TypeValue)
    assert alias.expr.value == 'int64'
    assert isinstance(value, hir.Declare)
    assert value.annotation == 'int64'


def test_compile_time_type_alias_is_removed_from_emitted_program() -> None:
    emitted = codegen(SrcFile(None, '''
let main = ():>Index => 42
const Index = <int64>
'''))

    assert 'Index' not in emitted
    assert 'let main = ():>int64' in emitted


def test_type_block_rejects_separate_type_expressions() -> None:
    with pytest.raises(UserError, match='one type expression'):
        check.typecheck_and_resolve(SrcFile(None, '<int64 string>'))
