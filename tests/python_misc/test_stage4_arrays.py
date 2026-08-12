import pytest

from src.cleanparse.backend.udewy import codegen
from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic import check, hir, ty
from src.cleanparse.semantic.errors import NotImplementedYet, TypeCheckError, UserError


def _check(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root


def _function_body(source: str) -> hir.Block:
    root = _check(source)
    declaration = root.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.FunctionLiteral)
    assert isinstance(declaration.expr.body, hir.Block)
    return declaration.expr.body


def test_inferred_array_has_int64_element_and_exact_length() -> None:
    body = _function_body(
        'let f = ():>int64 => { let values = [1 2 3] return values[1] }'
    )
    declaration = body.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.ArrayLiteral)
    assert declaration.expr.type == ty.ArrayType('int64', 3)
    returned = body.items[1]
    assert isinstance(returned, hir.Return)
    assert isinstance(returned.item, hir.Index)
    assert returned.item.constant_index == 1


def test_array_subtyping_forgets_length_but_keeps_elements_invariant() -> None:
    types = ty.TypeSystem()

    assert types.is_subtype(
        ty.ArrayType('int16', 3),
        ty.ArrayType('int16'),
    )
    assert not types.is_subtype(
        ty.ArrayType('int16'),
        ty.ArrayType('int16', 3),
    )
    assert not types.is_subtype(
        ty.ArrayType('int8', 3),
        ty.ArrayType('int16', 3),
    )


@pytest.mark.parametrize(
    ('type_name', 'minimum', 'maximum'),
    [
        ('int8', -128, 127),
        ('int16', -32768, 32767),
        ('int32', -2147483648, 2147483647),
        ('int64', -9223372036854775808, 9223372036854775807),
        ('uint8', 0, 255),
        ('uint16', 0, 65535),
        ('uint32', 0, 4294967295),
        ('uint64', 0, 18446744073709551615),
    ],
)
def test_fixed_width_array_literal_boundaries(
    type_name: str,
    minimum: int,
    maximum: int,
) -> None:
    _check(
        f'let f = ():>{type_name} => {{ '
        f'let values:array<{type_name}> = [{minimum} {maximum}] '
        'return values[0] }'
    )

    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check(f'let values:array<{type_name}> = [{maximum + 1}]')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check(f'let values:array<{type_name}> = [{minimum - 1}]')


def test_explicit_array_annotation_preserves_initializer_length() -> None:
    body = _function_body(
        'let f = ():>uint8 => { '
        'let values:array<uint8> = [1 2 3] '
        'return values[2] }'
    )
    declaration = body.items[0]
    assert isinstance(declaration, hir.Declare)
    assert declaration.annotation == ty.ArrayType('uint8')
    assert declaration.expr.type == ty.ArrayType('uint8', 3)


def test_array_length_is_an_exact_integer_and_proves_constant_expression() -> None:
    body = _function_body(
        'let f = ():>int64 => { '
        'let values = [10 20 30] '
        'return values[values.length - 1] }'
    )
    returned = body.items[1]
    assert isinstance(returned, hir.Return)
    assert isinstance(returned.item, hir.Index)
    assert returned.item.constant_index == 2
    assert isinstance(returned.item.index, hir.FunctionCall)
    length = returned.item.index.pos_args[0]
    assert isinstance(length, hir.ArrayLength)
    assert length.type == ty.IntegerLiteralType(3)


def test_const_integer_index_is_proven() -> None:
    body = _function_body(
        'let f = ():>int64 => { '
        'const index:int64 = 1 '
        'let values = [10 20] '
        'return values[index] }'
    )
    returned = body.items[2]
    assert isinstance(returned, hir.Return)
    assert isinstance(returned.item, hir.Index)
    assert returned.item.constant_index == 1


def test_indexed_assignment_has_dedicated_hir() -> None:
    body = _function_body(
        'let f = ():>int64 => { '
        'let values = [1 2] '
        'values[0] = 42 '
        'return values[0] }'
    )
    assignment = body.items[1]
    assert isinstance(assignment, hir.IndexAssign)
    assert assignment.target.constant_index == 0
    assert assignment.target.type == 'int64'


def test_const_array_elements_cannot_be_mutated() -> None:
    with pytest.raises(UserError, match='const array'):
        _check(
            'let f = ():>int64 => { '
            'const values = [1 2] '
            'values[0] = 42 '
            'return values[0] }'
        )


def test_array_diagnostics_cover_shape_elements_and_indices() -> None:
    with pytest.raises(TypeCheckError, match='empty array'):
        _check('let values = []')
    with pytest.raises(TypeCheckError, match='not homogeneous'):
        _check(
            'let left:int8 = 1 '
            'let right:uint8 = 2 '
            'let values = [left right]'
        )
    with pytest.raises(UserError, match='array index must be an integer'):
        _check('let values = [1 2] let value = values[true]')
    with pytest.raises(UserError, match='out of bounds'):
        _check('let values = [1 2] let value = values[2]')
    with pytest.raises(UserError, match='not proven in bounds'):
        _check(
            'let f = (index:int64):>int64 => { '
            'let values = [1 2] '
            'return values[index] }'
        )
    with pytest.raises(UserError, match='exact compile-time length'):
        _check('let f = (values:array<int64>):>int64 => values[0]')
    with pytest.raises(TypeCheckError, match='length mismatch'):
        _check('let values:array<int64 length=2> = [1]')


def test_initialization_checks_array_elements() -> None:
    with pytest.raises(UserError, match='used before initialization'):
        _check(
            'let get = ():>int64 => later '
            'let values:array<int64> = [get()] '
            'let later:int64 = 1'
        )


def test_width_specific_array_codegen() -> None:
    emitted = codegen(SrcFile(None, """
let f = ():>uint8 => {
    let bytes:array<uint8> = [1 2]
    bytes[1] = 42
    return bytes[1]
}
"""))

    assert '__alloca__(10) + 8' in emitted
    assert '__store_u8__(1 __dewy_array_1)' in emitted
    assert '__store_u8__(42 bytes + 1)' in emitted
    assert 'return __load_u8__(bytes + 1)' in emitted


@pytest.mark.parametrize(
    ('type_name', 'prefix', 'width', 'element_bytes'),
    [
        ('int8', 'i', 8, 1),
        ('int16', 'i', 16, 2),
        ('int32', 'i', 32, 4),
        ('int64', 'i', 64, 8),
        ('uint8', 'u', 8, 1),
        ('uint16', 'u', 16, 2),
        ('uint32', 'u', 32, 4),
        ('uint64', 'u', 64, 8),
    ],
)
def test_codegen_selects_each_fixed_width_layout(
    type_name: str,
    prefix: str,
    width: int,
    element_bytes: int,
) -> None:
    emitted = codegen(SrcFile(None, f"""
let f = ():>{type_name} => {{
    let values:array<{type_name}> = [1 2]
    return values[1]
}}
"""))

    assert f'__alloca__({8 + 2 * element_bytes}) + 8' in emitted
    assert f'__store_{prefix}{width}__(2 __dewy_array_1 + {element_bytes})' in emitted
    assert f'__load_{prefix}{width}__(values + {element_bytes})' in emitted


def test_udewy_rejects_array_returns_and_local_array_escapes() -> None:
    with pytest.raises(NotImplementedYet, match='array return values'):
        codegen(SrcFile(None, 'let make = ():>array<int64> => [1]'))

    with pytest.raises(NotImplementedYet, match='cannot escape'):
        codegen(SrcFile(None, """
let saved:array<int64> = [0]
let replace_saved = ():>void => {
    let local:array<int64> = [42]
    saved = local
}
"""))


def test_dynamic_index_uses_precise_source_position_facts() -> None:
    body = _function_body("""
let f = ():>int64 => {
    let values:array<int64> = [10 20 30]
    let i:int64 = 0
    let result:int64 = values[i]
    i = 3
    return result
}
""")

    declaration = body.items[2]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.Index)
    assert declaration.expr.constant_index == 0


def test_comparison_guards_and_arithmetic_prove_dynamic_indices() -> None:
    _check("""
let get = (i:int64):>int64 => {
    let values:array<int64> = [10 20 30]
    if 0 <=? i and i <? values.length - 1 {
        return values[i + 1]
    } else {
        return 0
    }
}
""")


def test_branch_merge_preserves_union_of_finite_bounds() -> None:
    _check("""
let get = (choose_first:bool):>int64 => {
    let values:array<int64> = [10 20 30]
    let i:int64 = 0
    if choose_first { i = 1 } else { i = 2 }
    return values[i]
}
""")


def test_loop_widening_reapplies_the_true_edge_bound() -> None:
    _check("""
let sum = ():>int64 => {
    let values:array<int64> = [10 20 12]
    let i:int64 = 0
    let total:int64 = 0
    loop i <? values.length {
        total += values[i]
        i += 1
    }
    return total
}
""")


def test_break_and_continue_paths_do_not_pollute_loop_backedges() -> None:
    _check("""
let sum = ():>int64 => {
    let values:array<int64> = [10 20 12]
    let i:int64 = 0
    let total:int64 = 0
    loop i <? values.length {
        if i =? 1 {
            i += 1
            continue
        }
        if i =? 2 {
            i = -1
            break
        }
        total += values[i]
        i += 1
    }
    return total
}
""")


@pytest.mark.parametrize(
    'source',
    [
        """
let get = (i:int64):>int64 => {
    let values:array<int64> = [10 20 30]
    return values[i]
}
""",
        """
let get = (i:int64):>int64 => {
    let values:array<int64> = [10 20 30]
    if i <? values.length { return values[i] } else { return 0 }
}
""",
        """
let get = ():>int64 => {
    let values:array<int64> = [10 20 30]
    let i:int64 = 0
    i = -1
    return values[i]
}
""",
    ],
)
def test_unproven_dynamic_indices_remain_hard_errors(source: str) -> None:
    with pytest.raises(UserError, match='not proven in bounds'):
        _check(source)


@pytest.mark.parametrize(
    ('range_source', 'first', 'last', 'count'),
    [
        ('0..2', 0, 2, 3),
        ('[0..3)', 0, 2, 3),
        ('(0..2]', 1, 2, 2),
        ('(0..3)', 1, 2, 2),
        ('2..1', 2, 1, 0),
    ],
)
def test_static_range_iterator_normalization(
    range_source: str,
    first: int,
    last: int,
    count: int,
) -> None:
    body = _function_body(f"""
let f = ():>int64 => {{
    let result:int64 = 0
    loop i in {range_source} {{ result += i }}
    return result
}}
""")
    flow = body.items[1]
    assert isinstance(flow, hir.Flow)
    condition = flow.arms[0].condition
    assert isinstance(condition, hir.IteratorExpression)
    assert (condition.first, condition.last, condition.count) == (
        first,
        last,
        count,
    )


def test_range_target_proves_indices_and_is_scoped_to_the_loop() -> None:
    _check("""
let sum = ():>int64 => {
    let values:array<int64> = [10 20 12]
    let total:int64 = 0
    loop i in [0..values.length) { total += values[i] }
    return total
}
""")

    with pytest.raises(UserError, match='undefined identifier `i`'):
        _check("""
let f = ():>int64 => {
    loop i in 0..1 {}
    return i
}
""")


def test_dynamic_index_codegen_keeps_width_aware_addressing() -> None:
    emitted = codegen(SrcFile(None, """
let f = ():>uint16 => {
    let values:array<uint16> = [1 2 3]
    let i:int64 = 0
    let result:uint16 = 0
    loop i <? values.length {
        values[i] = 42
        result = values[i]
        i += 1
    }
    return result
}
"""))

    assert '__store_u16__(42 values + (i * 2))' in emitted
    assert 'result = __load_u16__(values + (i * 2))' in emitted


def test_range_iterator_codegen_is_a_counted_loop() -> None:
    emitted = codegen(SrcFile(None, """
let f = ():>int64 => {
    let total:int64 = 0
    loop i in (0..3) {
        total += i
        continue
    }
    return total
}
"""))

    assert 'let __dewy_iterator_1:int64 = 0' in emitted
    assert 'loop __dewy_iterator_1 <? 2' in emitted
    assert '__dewy_iterator_value_1 = 1 + __dewy_iterator_1' in emitted
    assert '__dewy_iterator_1 += 1' in emitted
