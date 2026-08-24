import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError


def _check(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root


def test_array_place_is_explicit_in_signature_and_call_hir() -> None:
    root = _check('''
let mutate = (@items:array<int64 length=2>):>void => { items[0] = 40 }
let main = ():>void => {
    let values = [1 2]
    mutate(@values)
}
''')

    declaration = root.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.FunctionLiteral)
    parameter = declaration.expr.pos_or_kw_args[0]
    assert parameter.place
    assert isinstance(declaration.expr.type, ty.FunctionType)
    assert declaration.expr.type.pos_or_kw[0].place

    main = root.items[1]
    assert isinstance(main, hir.Declare)
    assert isinstance(main.expr, hir.FunctionLiteral)
    assert isinstance(main.expr.body, hir.Block)
    call = main.expr.body.items[1]
    assert isinstance(call, hir.FunctionCall)
    assert isinstance(call.pos_args[0], hir.Place)
    assert call.pos_args[0].target.name == 'values'


@pytest.mark.parametrize(
    ('source', 'message'),
    [
        (
            '''
let mutate = (@items:array<int64 length=2>):>void => void
let main = ():>void => { let values = [1 2] mutate(values) }
''',
            'place argument requires `@`',
        ),
        (
            '''
let read = (items:array<int64 length=2>):>void => void
let main = ():>void => { let values = [1 2] read(@values) }
''',
            'value parameter does not accept a place',
        ),
        (
            '''
let mutate = (@items:array<int64 length=2>):>void => void
let main = ():>void => { const values = [1 2] mutate(@values) }
''',
            'cannot pass a const binding as a mutable place',
        ),
        (
            '''
let both = (
    @left:array<int64 length=2>
    @right:array<int64 length=2>
):>void => void
let main = ():>void => { let values = [1 2] both(@values @values) }
''',
            'overlapping mutable places in one call',
        ),
    ],
)
def test_invalid_place_use_has_a_direct_diagnostic(
    source: str,
    message: str,
) -> None:
    with pytest.raises(UserError, match=message):
        _check(source)


def test_place_parameter_type_is_invariant() -> None:
    with pytest.raises(UserError, match='place parameter types are invariant'):
        _check('''
let mutate = (@items:array<int64>):>void => void
let main = ():>void => { let values = [1 2] mutate(@values) }
''')


def test_place_cannot_escape_an_immediate_call() -> None:
    with pytest.raises(
        TypeCheckError,
        match='a place can only be used as a function argument',
    ):
        _check('let values = [1 2]\nlet escaped = @values')


def test_place_parameters_cannot_have_defaults() -> None:
    with pytest.raises(UserError, match='place parameters cannot have defaults'):
        _check('''
let mutate = (
    @items:array<int64 length=2>=[1 2]
):>void => void
''')


def test_initial_place_slice_is_limited_to_array_bindings() -> None:
    with pytest.raises(
        NotImplementedYet,
        match='place parameters other than explicitly typed arrays',
    ):
        _check('let mutate = (@value:int64):>void => void')


def test_array_place_lowering_uses_a_non_escaping_pointer_cell() -> None:
    emitted = codegen(SrcFile(None, '''
let replace = (@items:array<int64 length=2>):>void => { items = [20 22] }
let main = ():>int64 => {
    let values = [1 2]
    replace(@values)
    return values[0] + values[1]
}
'''))

    assert 'let items:int64 = __load_i64__(__dewy_array_place_items_' in emitted
    assert '__store_i64__(items __dewy_array_place_items_' in emitted
    assert 'place_cell_values_' in emitted
    assert 'replace(__dewy_array_place_cell_values_' in emitted
    assert 'values = __load_i64__(__dewy_array_place_cell_values_' in emitted
