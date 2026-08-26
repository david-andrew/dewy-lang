from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError
from udewy.frontend import entry_point


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


def test_inferred_object_literal_fields_are_int64() -> None:
    body = _function_body(
        'let f = ():>int64 => { let o = [a = 10 b = 20] return o.a + o.b }'
    )
    declaration = body.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.ObjectLiteral)
    assert declaration.expr.type == ty.ObjectType((
        ty.ObjectField('a', 'int64'),
        ty.ObjectField('b', 'int64'),
    ))


def test_member_assign_has_dedicated_hir() -> None:
    body = _function_body(
        'let f = ():>int64 => { let o = [a = 10] o.a = 42 return o.a }'
    )
    assignment = body.items[1]
    assert isinstance(assignment, hir.MemberAssign)
    assert assignment.target.name == 'a'


def test_const_object_fields_cannot_be_mutated() -> None:
    with pytest.raises(UserError, match='const object'):
        _check(
            'let f = ():>int64 => { '
            'const o = [a = 10] '
            'o.a = 42 '
            'return o.a }'
        )


def test_const_field_cannot_be_mutated_through_mutable_object() -> None:
    with pytest.raises(UserError, match='const object field'):
        _check(
            'let f = ():>int64 => { '
            'let o = [const a = 10] '
            'o.a = 42 '
            'return o.a }'
        )


def test_named_object_type_alias_matches_literal() -> None:
    root = _check(
        'let Pair:type = [left:int64 right:int64]\n'
        'let f = ():>int64 => { let p:Pair = [left = 1 right = 2] return p.left }'
    )
    alias = root.items[0]
    assert isinstance(alias, hir.Declare)
    assert isinstance(alias.expr, hir.TypeValue)
    assert alias.expr.value == ty.ObjectType((
        ty.ObjectField('left', 'int64'),
        ty.ObjectField('right', 'int64'),
    ))


def test_object_type_desugars_colon_function_fields() -> None:
    root = _check(
        'let Box:type = [fn:(x:int64):>int64]\n'
        'let f = ():>int64 => {\n'
        '    let o:Box = [fn = (x:int64):>int64 => x]\n'
        '    return o.fn(42)\n'
        '}'
    )
    alias = root.items[0]
    assert isinstance(alias, hir.Declare)
    assert isinstance(alias.expr, hir.TypeValue)
    assert isinstance(alias.expr.value, ty.ObjectType)
    field = alias.expr.value.fields[0]
    assert field.name == 'fn'
    assert isinstance(field.type, ty.FunctionType)
    assert field.type.ret == 'int64'


def test_forward_and_nested_type_alias_dependencies_resolve() -> None:
    root = _check(
        'let Outer:type = [inner:Inner]\n'
        'let Inner:type = [value:int64]\n'
        'let f = (o:Outer):>int64 => o.inner.value'
    )
    outer = root.items[0]
    assert isinstance(outer, hir.Declare)
    assert isinstance(outer.expr, hir.TypeValue)
    assert outer.expr.value == ty.ObjectType((
        ty.ObjectField(
            'inner',
            ty.ObjectType((ty.ObjectField('value', 'int64'),)),
        ),
    ))


def test_cyclic_type_alias_is_rejected() -> None:
    with pytest.raises(UserError, match='cyclic type alias'):
        _check('let A:type = B\nlet B:type = A')


def test_zero_arg_member_is_auto_called() -> None:
    body = _function_body(
        'let f = ():>int64 => {\n'
        '    let o = [a = 40 fn2 = ():>int64 => a + 2]\n'
        '    return o.fn2\n'
        '}'
    )
    returned = body.items[1]
    assert isinstance(returned, hir.Return)
    assert isinstance(returned.item, hir.FunctionCall)
    assert isinstance(returned.item.func, hir.MemberAccess)
    assert returned.item.func.name == 'fn2'
    assert returned.item.pos_args == []


def test_expression_function_body_allows_grouped_compound_assignment() -> None:
    body = _function_body(
        'let f = ():>int64 => {\n'
        '    let value:int64 = 40\n'
        '    let increment = () => (value += 1)\n'
        '    return value\n'
        '}'
    )
    declaration = body.items[1]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.FunctionLiteral)
    assert isinstance(declaration.expr.body, hir.Block)
    assert len(declaration.expr.body.items) == 1
    assignment = declaration.expr.body.items[0]
    assert isinstance(assignment, hir.Assign)
    assert assignment.op == '+='


def test_ungrouped_compound_assignment_function_body_suggests_grouping() -> None:
    source = (
        'let f = ():>int64 => {\n'
        '    let value:int64 = 40\n'
        '    let increment = () => value += 1\n'
        '    return value\n'
        '}'
    )

    with pytest.raises(UserError) as caught:
        _check(source)

    report = caught.value.report
    assert report.title == 'function literal is not a valid compound assignment target'
    assert report.hint is not None
    assert 'wrap the in-place assignment in parentheses' in report.hint
    assert '() => (value += 1)' in report.hint


def test_object_method_can_compound_assign_a_sibling_field() -> None:
    emitted = codegen(SrcFile(None, '''
let counter = (start:int64=0) => [
    value = start
    increment = () => (value += 1)
]
let count = counter(40)
count.increment
count.increment
let main = ():>int64 => count.value
'''))

    assert '__store_i64__(__load_i64__(__dewy_object_self_' in emitted
    assert ' + 1 __dewy_object_self_' in emitted
    assert 'let main = ():>int64' in emitted


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
def test_homepage_counter_example_compiles_and_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = '''
counter = (start=0) => [
    value = start
    increment = () => (value += 1)
]

count = counter(40)
count.increment
count.increment

main = ():>int64 => count.value
'''
    path = tmp_path / 'counter.udewy'
    path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(path, []) == 42


def test_zero_arg_member_call_target_is_not_double_called() -> None:
    body = _function_body(
        'let f = ():>int64 => {\n'
        '    let o = [fn2 = ():>int64 => 42]\n'
        '    return o.fn2()\n'
        '}'
    )
    returned = body.items[1]
    assert isinstance(returned, hir.Return)
    assert isinstance(returned.item, hir.FunctionCall)
    assert isinstance(returned.item.func, hir.MemberAccess)
    assert returned.item.pos_args == []


def test_extracting_method_as_value_is_not_implemented() -> None:
    with pytest.raises(NotImplementedYet, match='function value'):
        _check(
            'let f = ():>int64 => {\n'
            '    let o = [add = (x:int64):>int64 => x]\n'
            '    let g = o.add\n'
            '    return (g)(42)\n'
            '}'
        )


def test_nonliteral_function_field_is_rejected_before_lowering() -> None:
    with pytest.raises(NotImplementedYet, match='non-literal function'):
        _check(
            'let inc = (x:int64):>int64 => x + 1\n'
            'let f = ():>int64 => { let o = [fn = inc] return o.fn(41) }'
        )


def test_reassigned_object_method_effect_is_not_treated_as_original() -> None:
    with pytest.raises(NotImplementedYet, match='initialization effect'):
        _check(
            'let Obj:type = [fn:():>int64]\n'
            'let make = ():>Obj => [fn = ():>int64 => y]\n'
            'let o:Obj = [fn = ():>int64 => 0]\n'
            'o = make()\n'
            'let result:int64 = o.fn()\n'
            'let y:int64 = 42\n'
            'let main = ():>int64 => result'
        )


def test_nested_function_cannot_capture_object_field() -> None:
    with pytest.raises(UserError, match='used before initialization'):
        _check(
            'let main = ():>int64 => {\n'
            '    let o = [\n'
            '        a = 42\n'
            '        outer = ():>int64 => {\n'
            '            let inner = ():>int64 => a\n'
            '            return inner()\n'
            '        }\n'
            '    ]\n'
            '    return o.outer\n'
            '}'
        )


def test_sequential_value_fields_can_read_earlier_fields() -> None:
    body = _function_body(
        'let f = ():>int64 => { let o = [a = 1 b = a + 1] return o.b }'
    )
    declaration = body.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.ObjectLiteral)


def test_array_length_counts_as_object_receiver_use() -> None:
    _check(
        'let f = ():>int64 => { '
        'let o = [a = [1 2] len = ():>int64 => a.length] '
        'return o.len }'
    )


def test_object_return_with_array_field_uses_recursive_result_storage() -> None:
    emitted = codegen(SrcFile(None, '''
let Box:type = [items:array<int64 length=2>]
let make = ():>Box => [items = [40 2]]
let main = ():>int64 => {
    let box = make()
    return box.items[0] + box.items[1]
}
'''))

    make_body, main_body = emitted.split('let main =', 1)
    assert '__alloca__(' not in make_body
    assert main_body.count('__alloca__(8)') == 1
    assert main_body.count('__alloca__(16)') == 1
    assert main_body.count('__alloca__(48)') == 1
    assert 'make(__dewy_object_' in main_body


def test_field_order_is_part_of_the_type() -> None:
    with pytest.raises(TypeCheckError, match='object fields'):
        _check(
            'let f = ():>int64 => {\n'
            '    let o:[a:int64 b:int64] = [b = 2 a = 1]\n'
            '    return o.a\n'
            '}'
        )


def test_object_types_require_exact_field_types() -> None:
    named = ty.ObjectType((
        ty.ObjectField(
            'fn',
            ty.FunctionType(
                [ty.PosOrKwArg('x', 'int64')],
                [],
                None,
                'int64',
            ),
        ),
    ))
    unnamed = ty.ObjectType((
        ty.ObjectField(
            'fn',
            ty.FunctionType(
                [ty.PosOrKwArg(None, 'int64')],
                [],
                None,
                'int64',
            ),
        ),
    ))
    types = ty.TypeSystem()
    assert not types.is_subtype(named, unnamed)
    assert not types.is_subtype(unnamed, named)


def test_dictionary_declarations_are_branded_objects() -> None:
    # A dictionary is the runtime object `[keys values]` branded `dict`.
    root = _check('let d = [1 -> 2]')
    declared = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'd')
    assert isinstance(declared.expr, hir.ObjectLiteral)
    assert ty.dict_key_value(declared.expr.type) == ('int64', 'int64')  # literal entries widen to words
    assert [f.name for f in declared.expr.type.fields] == ['keys', 'values', 'hashes', 'indices', 'live']
    assert declared.expr.type != ty.ObjectType(declared.expr.type.fields)  # the brand distinguishes it


def test_dictionary_literals_outside_declarations() -> None:
    root = _check('let d = ([1 -> 2])\nlet e:dict<int64 int64> = []')
    names = {item.name: item for item in root.items if isinstance(item, hir.Declare)}
    assert ty.dict_key_value(names['d'].expr.type) is not None
    assert ty.dict_key_value(names['e'].expr.type) == ('int64', 'int64')


def test_runtime_type_values_are_not_implemented() -> None:
    with pytest.raises(NotImplementedYet, match='runtime type'):
        _check(
            'let Pair:type = [left:int64]\n'
            'let f = ():>int64 => { let t = Pair return 0 }'
        )


def test_empty_brackets_stay_unconstrained() -> None:
    with pytest.raises(TypeCheckError, match='empty array'):
        _check('let f = ():>int64 => { let values = [] return 0 }')
