import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError, UserError


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


def test_place_parameter_requires_an_explicit_type() -> None:
    with pytest.raises(UserError, match='place parameters require an explicit type'):
        _check('let mutate = (@value):>void => void')


def test_scalar_and_object_places_are_preserved_in_hir() -> None:
    root = _check('''
let Pair:type = [left:int64 right:int64]
let update_number = (@value:int64):>void => { value += 1 }
let update_pair = (@pair:Pair):>void => { pair.left = 20 }
''')

    number = root.items[1]
    pair = root.items[2]
    assert isinstance(number, hir.Declare)
    assert isinstance(number.expr, hir.FunctionLiteral)
    assert number.expr.pos_or_kw_args[0].place
    assert number.expr.pos_or_kw_args[0].type == 'int64'
    assert isinstance(pair, hir.Declare)
    assert isinstance(pair.expr, hir.FunctionLiteral)
    assert pair.expr.pos_or_kw_args[0].place
    assert isinstance(pair.expr.pos_or_kw_args[0].type, ty.ObjectType)


def test_field_and_index_selectors_project_a_place_route() -> None:
    root = _check('''
let Pair:type = [left:int64 right:int64]
let set = (@value:int64):>void => { value = 42 }
let main = ():>void => {
    let pair:Pair = [left = 1 right = 2]
    let values:array<int64 length=2> = [3 4]
    set(@pair.left)
    set(@values[1])
    set(@(pair.right))
}
''')

    main = root.items[2]
    assert isinstance(main, hir.Declare)
    assert isinstance(main.expr, hir.FunctionLiteral)
    assert isinstance(main.expr.body, hir.Block)
    field_call, index_call, grouped_call = main.expr.body.items[2:]
    assert isinstance(field_call, hir.FunctionCall)
    assert isinstance(field_call.pos_args[0], hir.Place)
    assert isinstance(field_call.pos_args[0].target, hir.MemberAccess)
    assert isinstance(index_call, hir.FunctionCall)
    assert isinstance(index_call.pos_args[0], hir.Place)
    assert isinstance(index_call.pos_args[0].target, hir.Index)
    assert isinstance(grouped_call, hir.FunctionCall)
    assert isinstance(grouped_call.pos_args[0], hir.Place)
    assert isinstance(grouped_call.pos_args[0].target, hir.MemberAccess)


def test_disjoint_projected_places_can_share_one_call() -> None:
    _check('''
let Pair:type = [left:int64 right:int64]
let set_both = (@left:int64 @right:int64):>void => {
    left = 20
    right = 22
}
let main = ():>void => {
    let pair:Pair = [left = 1 right = 2]
    let values:array<int64 length=2> = [3 4]
    set_both(@pair.left @pair.right)
    set_both(@values[0] @values[1])
}
''')


def test_potentially_overlapping_place_routes_are_rejected() -> None:
    with pytest.raises(UserError, match='overlapping mutable places in one call'):
        _check('''
let Pair:type = [left:int64 right:int64]
let conflict = (@whole:Pair @part:int64):>void => void
let main = ():>void => {
    let pair:Pair = [left = 1 right = 2]
    conflict(@pair @pair.left)
}
''')


@pytest.mark.parametrize(
    'argument',
    ['@pair.left', '@values[0]'],
)
def test_projected_place_cannot_descend_from_const_root(argument: str) -> None:
    source = f'''
let Pair:type = [left:int64 right:int64]
let set = (@value:int64):>void => void
let main = ():>void => {{
    const pair:Pair = [left = 1 right = 2]
    const values:array<int64 length=2> = [3 4]
    set({argument})
}}
'''
    with pytest.raises(UserError, match='const'):
        _check(source)


def test_array_place_lowering_uses_a_non_escaping_pointer_cell() -> None:
    emitted = codegen(SrcFile(None, '''
let replace = (@items:array<int64 length=2>):>void => { items = [20 22] }
let main = ():>int64 => {
    let values = [1 2]
    replace(@values)
    return values[0] + values[1]
}
'''))

    assert 'let items:int64 = __load_i64__(__dewy_place_items_' in emitted
    assert '__store_i64__(items __dewy_place_items_' in emitted
    assert '__dewy_place_cell_values_' in emitted
    assert 'replace(__dewy_place_cell_values_' in emitted
    assert 'values = __load_i64__(__dewy_place_cell_values_' in emitted


def test_scalar_place_lowering_uses_typed_cell_loads_and_stores() -> None:
    emitted = codegen(SrcFile(None, '''
let bump = (@value:int64):>void => { value += 2 }
let main = ():>int64 => {
    let value:int64 = 40
    bump(@value)
    return value
}
'''))

    assert 'let value:int64 = __load_i64__(__dewy_place_value_' in emitted
    assert '__store_i64__(value __dewy_place_value_' in emitted
    assert 'bump(__dewy_place_cell_value_' in emitted
    assert 'value = __load_i64__(__dewy_place_cell_value_' in emitted


def test_object_place_lowering_passes_structural_storage_directly() -> None:
    emitted = codegen(SrcFile(None, '''
let Pair:type = [left:int64 right:int64]
let replace = (@pair:Pair):>void => { pair = [left = 20 right = 22] }
let main = ():>int64 => {
    let pair:Pair = [left = 1 right = 2]
    replace(@pair)
    return pair.left + pair.right
}
'''))

    assert 'let pair:int64 = __dewy_place_pair_' in emitted
    assert 'replace(pair)' in emitted
    assert 'place_cell_pair' not in emitted


def test_projected_place_lowering_passes_the_final_storage_address() -> None:
    emitted = codegen(SrcFile(None, '''
let Pair:type = [left:int64 right:int64]
let set = (@value:int64):>void => { value = 42 }
let main = ():>int64 => {
    let pair:Pair = [left = 1 right = 2]
    let values:array<int64 length=2> = [3 4]
    set(@pair.right)
    set(@values[0])
    return pair.right + values[0] - 42
}
'''))

    assert 'set(pair + 8)' in emitted
    assert 'set(values)' in emitted
    assert 'place_cell_pair' not in emitted
    assert 'place_cell_values' not in emitted
