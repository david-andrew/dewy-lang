import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet
from dewy.semantic.hir_display import hir_to_dewy, hir_to_tree_str


def _function(source: str, name: str = 'f') -> hir.FunctionLiteral:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    declaration = next(
        item
        for item in root.items
        if isinstance(item, hir.Declare) and item.name == name
    )
    assert isinstance(declaration.expr, hir.FunctionLiteral)
    return declaration.expr


def test_juxtaposed_semicolon_suppresses_an_expressed_value() -> None:
    function = _function('let f = () => { 42; }')

    assert function.rettype == 'void'
    assert isinstance(function.body, hir.Block)
    suppressed = function.body.items[0]
    assert isinstance(suppressed, hir.Suppress)
    assert suppressed.type == 'void'
    assert isinstance(suppressed.item, hir.Integer)
    assert hir_to_dewy(suppressed) == '42;'
    assert hir_to_tree_str(suppressed) == 'Suppress\n└── item: Integer(42)'


def test_suppression_preserves_effects_without_becoming_the_return_value() -> None:
    source = '''
let answer = ():>int64 => 40
let f = () => {
    answer();
    42
}
'''
    function = _function(source)
    assert isinstance(function.rettype, ty.IntegerLiteralType)
    assert function.rettype.value == 42

    emitted = codegen(SrcFile(None, source))
    assert 'answer()\n    return 42' in emitted


def test_suppression_allows_a_bare_expression_before_explicit_return() -> None:
    emitted = codegen(SrcFile(None, '''
let f = ():>int64 => {
    40;
    return 42
}
'''))

    assert '40\n    return 42' in emitted


def test_suppressing_a_nonreturning_expression_remains_nonreturning() -> None:
    source = 'let f = ():>int64 => { (return 42); }'
    function = _function(source)

    assert isinstance(function.body, hir.Block)
    suppressed_return = function.body.items[0]
    assert isinstance(suppressed_return, hir.Suppress)
    assert suppressed_return.type == ty.BOTTOM_TYPE
    assert hir_to_dewy(suppressed_return) == '(return 42);'
    assert 'return 42' in codegen(SrcFile(None, source))


def test_unattached_semicolon_remains_reserved_for_array_dimensions() -> None:
    with pytest.raises(NotImplementedYet, match='standalone semicolon array-dimension syntax'):
        check.typecheck_and_resolve(SrcFile(None, 'let f = () => { 42 ; }'))
