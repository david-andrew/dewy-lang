import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError


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


def _multi_condition(source: str) -> hir.MultiIteratorExpression:
    body = _function_body(source)
    flow = next(item for item in body.items if isinstance(item, hir.Flow))
    condition = flow.arms[0].condition
    assert isinstance(condition, hir.MultiIteratorExpression)
    return condition


def test_undefined_is_a_value_distinct_from_void() -> None:
    root = _check(
        'let f = ():>int64|undefined => undefined'
    )
    declaration = root.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.FunctionLiteral)
    assert isinstance(declaration.expr.body, hir.Undefined)
    assert declaration.expr.body.type == 'undefined'


def test_optional_type_guards_refine_both_edges() -> None:
    _check("""
let get = (value:int64|undefined):>int64 => {
    if value is? int64 {
        return value + 1
    } else if value isnt? undefined {
        return value
    } else {
        return 41
    }
}
""")

    with pytest.raises(TypeCheckError, match='no matching overload'):
        _check(
            'let get = (value:int64|undefined):>int64 => value + 1'
        )


def test_assignment_invalidates_an_optional_refinement() -> None:
    with pytest.raises(TypeCheckError, match='no matching overload'):
        _check("""
let get = (value:int64|undefined):>int64 => {
    if value isnt? undefined {
        value = undefined
        return value + 1
    }
    return 0
}
""")


def test_short_circuit_rhs_uses_the_guard_refinement() -> None:
    _check("""
let positive = (value:int64|undefined):>bool =>
    if value isnt? undefined and value >? 0 true else false
""")
    _check("""
let get = (value:int64|undefined):>int64 =>
    if value not is? undefined value else 0
""")


def test_heterogeneous_runtime_union_bindings_lower() -> None:
    # General tagged unions now lower as tag-and-payload cells, including a
    # heterogeneous union containing `undefined`.
    source = 'let main = ():>int64 => { let x:int64|string|undefined = 1 return 0 }'
    emitted = codegen(SrcFile(None, source))
    assert '__store_u8__' in emitted


def test_multiiterator_uses_flat_postfix_formula_and_precise_optionals() -> None:
    condition = _multi_condition("""
let f = ():>int64 => {
    let result:int64 = 0
    loop a in 0..1 and b in 0..2 or c in 0..3 {
        result += c
    }
    return result
}
""")

    assert condition.formula == [0, 1, 'and', 2, 'or']
    assert [iterator.target.type for iterator in condition.iterators] == [
        ty.optional('int64'),
        ty.optional('int64'),
        'int64',
    ]
    assert not condition.repeats_when_exhausted


def test_symbolic_iterator_operators_match_spelled_forms() -> None:
    symbolic = _multi_condition("""
let f = ():>int64 => {
    loop a in 0..1 & b in 0..2 | c in 0..3 {}
    return 0
}
""")
    spelled = _multi_condition("""
let f = ():>int64 => {
    loop a in 0..1 and b in 0..2 or c in 0..3 {}
    return 0
}
""")

    assert symbolic.formula == spelled.formula


def test_and_zip_shortest_keeps_all_targets_defined() -> None:
    condition = _multi_condition("""
let f = ():>int64 => {
    loop a in 0..1 and b in 0..4 {}
    return 0
}
""")

    assert [iterator.target.type for iterator in condition.iterators] == [
        'int64',
        'int64',
    ]


def test_all_exhausted_literal_truth_can_repeat_forever() -> None:
    condition = _multi_condition("""
let f = ():>int64 => {
    loop a in 1..0 nor b in 1..0 { break }
    return 0
}
""")

    assert condition.repeats_when_exhausted
    assert all(
        ty.optional_payload(iterator.target.type) == 'int64'
        for iterator in condition.iterators
    )


def test_multiiterator_rejects_duplicate_targets_and_mixed_predicates() -> None:
    with pytest.raises(UserError, match='duplicate iterator target'):
        _check("""
let f = ():>int64 => {
    loop i in 0..1 and i in 0..2 {}
    return 0
}
""")

    with pytest.raises(NotImplementedYet, match='mixed Boolean and iterator'):
        _check("""
let f = (keep_going:bool):>int64 => {
    loop i in 0..1 and keep_going {}
    return 0
}
""")


def test_optional_iterator_target_can_index_after_narrowing() -> None:
    _check("""
let get = ():>int64 => {
    let values:array<int64> = [10 20 12]
    let result:int64 = 0
    loop i in 0..1 or j in 0..2 {
        if i is? int64 {
            result += values[i]
        }
    }
    return result
}
""")


def test_multiiterator_codegen_is_eager_and_eliminates_rich_hir() -> None:
    emitted = codegen(SrcFile(None, """
let f = ():>int64 => {
    let result:int64 = 0
    loop i in 0..1 or j in 0..2 {
        if i isnt? undefined { result += i }
        result += j
        continue
    }
    return result
}
"""))

    first_update = emitted.index('__dewy_iterator_active_3 =')
    second_update = emitted.index('__dewy_iterator_active_4 =')
    source_continue = emitted.index('continue', second_update)
    assert first_update < second_update < source_continue
    assert emitted.count('__dewy_iterator_1 += 1') == 1
    assert emitted.count('__dewy_iterator_2 += 1') == 1
    assert 'undefined' not in emitted
    assert ' in [' not in emitted


def test_dict_unpacking_builds_lockstep_array_iterators() -> None:
    root = _check('''
let pairs = ['a' -> 1 'b' -> 2]
loop [k v] in pairs {}
''')
    flow = next(item for item in root.items if isinstance(item, hir.Flow))
    condition = flow.arms[0].condition
    assert isinstance(condition, hir.MultiIteratorExpression)
    assert len(condition.iterators) == 2
    assert condition.formula == [0, 1, 'and']
    keys, values = condition.iterators
    assert keys.target.name == 'k'
    assert values.target.name == 'v'
    assert isinstance(keys.iterable.type, ty.ArrayType)
    assert keys.count == 2
    assert values.count == 2


def test_dict_unpacking_over_arrays_is_not_implemented() -> None:
    with pytest.raises(NotImplementedYet, match='non-dictionary'):
        _check('let pairs = [[1 2] [3 4]] loop [a b] in pairs {}')


def test_dict_unpacking_requires_two_targets() -> None:
    with pytest.raises(UserError, match='exactly two targets'):
        _check("let d = ['a' -> 1] loop [a b c] in d {}")


def test_diverging_if_arms_narrow_the_continuation() -> None:
    root = _check('''
let f = (v:int64|string):>int64 => {
    if v is? int64 { return v }
    return v.length
}
''')
    # Typechecks at all only because `v` is `string` after the early return.
    assert isinstance(root.items[0], hir.Declare)


def test_non_diverging_if_arms_do_not_narrow() -> None:
    with pytest.raises((TypeCheckError, UserError)):
        _check('''
let f = (v:int64|string):>int64 => {
    if v is? int64 { let x = v }
    return v.length
}
''')
