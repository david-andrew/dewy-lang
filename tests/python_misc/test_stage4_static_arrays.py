from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.backend.udewy.lower import ArrayRepresentation, ArrayUse, _Lowerer
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from udewy.frontend import entry_point


def _analyze_arrays(source: str) -> tuple[_Lowerer, dict[str, int]]:
    srcfile = SrcFile(None, source)
    root = check.typecheck_and_resolve(srcfile)
    assert isinstance(root, hir.Block)
    lowerer = _Lowerer(root, srcfile)
    lowerer._discover_block(
        root,
        lowerer.module_scope,
        current_function=None,
        create_scope=False,
        function_body=False,
    )
    lowerer._classify_array_representations()
    names = {
        binding.name: binding_id
        for binding_id, binding in lowerer.binding_by_semantic_id.items()
    }
    return lowerer, names


def _classify_array_representations(
    source: str,
) -> tuple[dict[str, ArrayRepresentation], dict[str, set[ArrayUse]]]:
    lowerer, _ = _analyze_arrays(source)
    names = {
        binding_id: binding.name
        for binding_id, binding in lowerer.binding_by_semantic_id.items()
    }
    representations: dict[str, ArrayRepresentation] = {
        names[binding_id]: representation
        for binding_id, representation in lowerer.array_representations.items()
    }
    uses = {
        names[binding_id]: array_uses
        for binding_id, array_uses in lowerer.array_uses.items()
        if binding_id in lowerer.array_representations
    }
    return representations, uses


def test_fixed_local_array_uses_are_classified_as_stack_data() -> None:
    representations, uses = _classify_array_representations('''
const module_values:array<int64> = [1 2]
let read = ():>int64 => {
    let mutable_values:array<int64> = [10 20]
    mutable_values[0] = 40
    return mutable_values[0] + mutable_values.length
}
let read_const = ():>int64 => {
    const const_values = [20 22]
    return const_values[1]
}
''')

    assert representations['mutable_values'] == 'stack_data'
    assert representations['const_values'] == 'stack_data'
    assert representations['module_values'] == 'static_words'
    assert uses['mutable_values'] == {'length', 'index_read', 'index_write'}
    assert uses['const_values'] == {'index_read'}


def test_transitive_local_alias_group_propagates_stack_data() -> None:
    lowerer, names = _analyze_arrays('''
let read = ():>int64 => {
    let values = [1 2]
    let alias = values
    let transitive = alias
    transitive[0] = 40
    return alias[0] + values.length
}
''')
    values = names['values']
    alias = names['alias']
    transitive = names['transitive']

    assert lowerer.array_alias_edges == {
        alias: values,
        transitive: alias,
    }
    group_id = lowerer.array_alias_group_by_binding[values]
    assert lowerer.array_alias_groups[group_id] == {values, alias, transitive}
    assert lowerer.array_group_uses[group_id] == {
        'alias',
        'length',
        'index_read',
        'index_write',
    }
    assert {
        lowerer.array_representations[binding_id]
        for binding_id in (values, alias, transitive)
    } == {'stack_data'}


def test_array_parameter_local_copy_does_not_make_parameter_writable() -> None:
    lowerer, names = _analyze_arrays('''
let update = (items:array<int64 length=2>):>int64 => {
    let view = items
    view[0] = 40
    return view[0] + items.length
}
''')
    items = names['items']
    view = names['view']
    analysis = lowerer.array_parameter_analyses[items]

    assert analysis.alias_group == {items, view}
    assert analysis.uses == {'length'}
    assert analysis.adapter_safe


@pytest.mark.parametrize(
    ('source', 'unsafe_use'),
    [
        (
            '''
let convert = (items:array<grapheme length=2>):>string =>
    items as string
''',
            'representation',
        ),
        (
            '''
let replace = (items:array<int64 length=2>):>int64 => {
    let replacement = [40 2]
    items = replacement
    return items[0]
}
''',
            'representation',
        ),
    ],
)
def test_array_parameter_unsafe_uses_require_descriptors(
    source: str,
    unsafe_use: ArrayUse,
) -> None:
    lowerer, names = _analyze_arrays(source)
    parameter_name = 'forwarded' if 'forwarded' in names else 'items'
    analysis = lowerer.array_parameter_analyses[names[parameter_name]]

    assert unsafe_use in analysis.uses
    assert not analysis.adapter_safe


@pytest.mark.parametrize(
    'source',
    [
        '''
let escape = (items:array<int64 length=2>):>array<int64 length=2> =>
    items
''',
        '''
let store = (items:array<int64 length=2>):>int64 => {
    let box = [value = items]
    return box.value[0]
}
''',
    ],
)
def test_read_only_returns_and_stores_are_adapter_safe(source: str) -> None:
    # Returning the parameter or storing it into an object field copies the
    # value at that site, so the effect analysis proves the parameter itself
    # is only read and its storage may be borrowed across the call.
    lowerer, names = _analyze_arrays(source)
    analysis = lowerer.array_parameter_analyses[names['items']]

    assert 'representation' in analysis.uses
    assert analysis.adapter_safe


def test_array_parameter_read_only_forwarding_is_adapter_safe() -> None:
    lowerer, names = _analyze_arrays('''
let first = (items:array<int64 length=2>):>int64 => items[0]
let forward = (forwarded:array<int64 length=2>):>int64 =>
    first(forwarded)
''')
    analysis = lowerer.array_parameter_analyses[names['forwarded']]

    assert analysis.uses == {'safe_call_boundary'}
    assert analysis.adapter_safe


def test_nested_array_write_marks_outer_parameter_writable() -> None:
    lowerer, names = _analyze_arrays('''
let update = (
    items:array<array<int64 length=2> length=2>
):>int64 => {
    items[0][0] = 40
    return items[0][0]
}
''')
    analysis = lowerer.array_parameter_analyses[names['items']]

    assert 'index_write' in analysis.uses
    assert not analysis.adapter_safe


def test_safe_direct_call_boundary_preserves_local_alias_stack_data() -> None:
    lowerer, names = _analyze_arrays('''
let first = (items:array<int64 length=2>):>int64 => items[0]
let read = ():>int64 => {
    let values = [42 0]
    let alias = values
    return first(alias)
}
''')
    values = names['values']
    alias = names['alias']
    boundary = next(iter(lowerer.array_call_boundary_analyses.values()))

    assert boundary.safe
    assert boundary.function is not None
    assert boundary.function.logical_name == 'first'
    assert boundary.parameter is not None
    assert boundary.parameter.name == 'items'
    assert boundary.position == 0
    assert boundary.source_binding_id == alias
    assert boundary.source_alias_group == {values, alias}
    assert lowerer.array_group_uses[
        lowerer.array_alias_group_by_binding[values]
    ] == {'alias', 'safe_call_boundary'}
    assert lowerer.array_representations[values] == 'stack_data'
    assert lowerer.array_representations[alias] == 'stack_data'


def test_selected_overload_records_one_safe_array_boundary() -> None:
    lowerer, names = _analyze_arrays('''
let read_array = (items:array<int64 length=2>):>int64 => items[0]
let identity = (value:int64):>int64 => value
let selected = @read_array & @identity
let read = ():>int64 => {
    let values = [42 0]
    return selected(values)
}
''')
    boundary = next(iter(lowerer.array_call_boundary_analyses.values()))

    assert boundary.safe
    assert boundary.function is not None
    assert boundary.function.logical_name == 'read_array'
    assert lowerer.array_representations[names['values']] == 'stack_data'


def test_read_only_static_call_boundaries_preserve_raw_tables() -> None:
    lowerer, names = _analyze_arrays('''
const words:array<int64> = [40 2]
const bytes:array<uint8> = 0x"2802"
let read_words = (items:array<int64 length=2>):>int64 => items[0]
let read_bytes = (items:array<uint8 length=2>):>uint8 => items[0]
let read = ():>int64 => {
    let ignored:uint8 = read_bytes(bytes)
    return read_words(words) + 2
}
''')

    assert lowerer.array_representations[names['words']] == 'static_words'
    assert lowerer.array_representations[names['bytes']] == 'static_bytes'
    assert all(
        boundary.safe
        for boundary in lowerer.array_call_boundary_analyses.values()
    )


def test_writable_static_bytes_call_boundary_copies_from_static_data() -> None:
    lowerer, names = _analyze_arrays('''
const bytes:array<uint8> = 0x"2802"
let mutate = (items:array<uint8 length=2>):>uint8 => {
    items[0] = 42
    return items[0]
}
let read = ():>uint8 => mutate(bytes)
''')
    boundary = next(iter(lowerer.array_call_boundary_analyses.values()))

    assert not boundary.safe
    assert lowerer.array_representations[names['bytes']] == 'static_bytes'
    assert 'copy_call_boundary' in lowerer.array_uses[names['bytes']]


@pytest.mark.parametrize(
    ('source', 'expected_representation', 'expected_safe'),
    [
        (
            '''
let first = (items:array<int64 length=2>):>int64 => items[0]
let read = ():>int64 => {
    let indirect = @first
    let values = [42 0]
    return indirect(values)
}
''',
            'stack_data',
            False,
        ),
        (
            '''
let first = (items:array<int64 length=2>):>int64 => items[0]
let forward = (forwarded:array<int64 length=2>):>int64 =>
    first(forwarded)
let read = ():>int64 => {
    let values = [42 0]
    return forward(values)
}
''',
            'stack_data',
            True,
        ),
        (
            '''
let first = (items:array<int64 length=2>):>int64 => items[0]
let read = (choose_left:bool):>int64 => {
    let values = if choose_left { [42 0] } else { [0 42] }
    return first(values)
}
''',
            'descriptor',
            True,
        ),
        (
            '''
let store = (items:array<int64 length=2>):>int64 => {
    let box = [value = items]
    return box.value[0]
}
let read = ():>int64 => {
    let values = [42 0]
    return store(values)
}
''',
            'stack_data',
            True,
        ),
        (
            '''
let read = ():>int64 => {
    let reader = [
        apply = (items:array<int64 length=2>):>int64 => items[0]
    ]
    let values = [42 0]
    return reader.apply(values)
}
''',
            'stack_data',
            False,
        ),
    ],
)
def test_array_call_boundaries_preserve_source_representation(
    source: str,
    expected_representation: ArrayRepresentation,
    expected_safe: bool,
) -> None:
    lowerer, names = _analyze_arrays(source)
    values = names['values']
    boundary = next(
        boundary
        for boundary in lowerer.array_call_boundary_analyses.values()
        if boundary.source_binding_id == values
    )

    assert lowerer.array_representations[values] == expected_representation
    assert boundary.safe is expected_safe
    expected_use: ArrayUse = (
        'safe_call_boundary' if expected_safe else 'copy_call_boundary'
    )
    assert expected_use in lowerer.array_uses[values]


def test_local_array_copy_then_read_only_call_uses_independent_storage() -> None:
    emitted = codegen(SrcFile(None, '''
let first = (items:array<int64 length=2>):>int64 => items[0]
let read = ():>int64 => {
    let values = [42 0]
    let alias = values
    return first(alias)
}
'''))

    assert 'let values:int64 = __alloca__(16)' in emitted
    assert 'let alias:int64 = __alloca__(16)' in emitted
    assert '__store_i64__(__load_i64__(values) alias)' in emitted
    assert '__store_i64__(__load_i64__(values + 8) alias + 8)' in emitted
    assert emitted.count('__alloca__(16)') == 2
    assert emitted.count('__alloca__(48)') == 1
    assert '__store_i64__(alias __dewy_array_1)' in emitted
    assert '__store_i64__(2 __dewy_array_1 + 8)' in emitted
    assert '__store_i64__(2 __dewy_array_1 + 16)' in emitted
    assert '__store_i64__(8 __dewy_array_1 + 24)' in emitted
    assert '__store_i64__(1 __dewy_array_1 + 32)' in emitted
    assert '__store_i64__(0 __dewy_array_1 + 40)' in emitted
    assert 'return first(__dewy_array_1)' in emitted
    assert '__dewy_array_data_' not in emitted


def test_static_call_adapters_preserve_storage_flags() -> None:
    emitted = codegen(SrcFile(None, '''
const words:array<int64> = [40 2]
const bytes:array<uint8> = 0x"2802"
let read_words = (items:array<int64 length=2>):>int64 => items[0]
let read_bytes = (items:array<uint8 length=2>):>int64 => {
    if items[0] =? 40 and items[1] =? 2 { return 42 } else { return 1 }
}
let read = ():>int64 => {
    let ignored:int64 = read_words(words)
    return read_bytes(bytes)
}
'''))

    assert 'const words:int64 = __static_words__(40 2)' in emitted
    assert 'const bytes:int64 = 0x"2802"' in emitted
    assert emitted.count('__alloca__(48)') == 2
    assert '__store_i64__(words __dewy_array_1)' in emitted
    assert '__store_i64__(8 __dewy_array_1 + 24)' in emitted
    assert '__store_i64__(1 __dewy_array_1 + 32)' in emitted
    assert '__store_i64__(bytes __dewy_array_2)' in emitted
    assert '__store_i64__(1 __dewy_array_2 + 24)' in emitted
    assert '__store_i64__(2 __dewy_array_2 + 32)' in emitted


def test_selected_overload_call_uses_descriptor_adapter() -> None:
    emitted = codegen(SrcFile(None, '''
let read_array = (items:array<int64 length=2>):>int64 => items[0]
let identity = (value:int64):>int64 => value
let selected = @read_array & @identity
let read = ():>int64 => {
    let values = [42 0]
    return selected(values)
}
'''))

    assert 'let values:int64 = __alloca__(16)' in emitted
    assert 'let __dewy_array_1:int64 = __alloca__(48)' in emitted
    assert '__store_i64__(values __dewy_array_1)' in emitted
    assert 'return read_array(__dewy_array_1)' in emitted


def test_multiple_call_adapters_preserve_argument_order() -> None:
    emitted = codegen(SrcFile(None, '''
let sum = (
    left:array<int64 length=1>
    right:array<int64 length=1>
):>int64 => left[0] + right[0]
let read = ():>int64 => {
    let left = [20]
    let right = [22]
    return sum(left right)
}
'''))

    left_adapter = emitted.index('__store_i64__(left __dewy_array_1)')
    right_adapter = emitted.index('__store_i64__(right __dewy_array_2)')
    call = emitted.index('return sum(__dewy_array_1 __dewy_array_2)')
    assert left_adapter < right_adapter < call


@pytest.mark.parametrize(
    ('name', 'source'),
    [
        (
            'values',
            '''
let read = ():>int64 => {
    let values = [20 22]
    let replacement = [40 2]
    values = replacement
    return values[1]
}
''',
        ),
        (
            'values',
            '''
let make = ():>array<int64 length=2> => {
    let values = [42 0]
    return values
}
''',
        ),
        (
            'values',
            '''
let read = ():>int64 => {
    let values = [42 0]
    let box = [items = values]
    return box.items[0]
}
''',
        ),
        (
            'values',
            '''
let read = ():>string => {
    let values:array<grapheme> = ['o' 'k']
    return values as string
}
''',
        ),
        (
            'values',
            '''
let make = ():>array<int64 length=2> => [42 0]
let read = ():>int64 => {
    let values = make()
    return values[0]
}
''',
        ),
        (
            'values',
            '''
let read = ():>uint8 => {
    let values:array<uint8> = 0x"2a00"
    return values[0]
}
''',
        ),
        (
            'values',
            '''
let read = ():>uint8 => {
    let values:array<uint8> = 0x"2a00"
    let alias = values
    return alias[0]
}
''',
        ),
        (
            'values',
            '''
const values = [42 0]
const alias = values
let read = ():>int64 => alias[0]
''',
        ),
        (
            'values',
            '''
let read = ():>int64 => {
    let values = [42 0]
    let nested = ():>int64 => {
        let alias = values
        return alias[0]
    }
    return nested()
}
''',
        ),
        (
            'left',
            '''
let read = (choose_left:bool):>int64 => {
    let left = [42 0]
    let right = [0 42]
    let selected = if choose_left { left } else { right }
    return selected[0]
}
''',
        ),
    ],
)
def test_local_array_representation_uses_keep_descriptors(
    name: str,
    source: str,
) -> None:
    representations, _ = _classify_array_representations(source)

    assert representations[name] == 'descriptor'


def test_module_const_word_array_uses_static_storage() -> None:
    emitted = codegen(SrcFile(None, '''
const forty:int64 = 40
const words:array<int64> = [forty 2]
let main = ():>int64 => words[0] + words[1] + words.length - 2
'''))

    assert 'const words:int64 = __static_words__(40 2)' in emitted
    assert '__load_i64__(words)' in emitted
    assert '__load_i64__(words + 8)' in emitted
    assert '__static_alloca__(16)' not in emitted
    assert '__static_alloca__(48)' not in emitted
    assert '__store_i64__(40 ' not in emitted


def test_module_const_function_array_uses_typed_static_words() -> None:
    emitted = codegen(SrcFile(None, '''
let increment = (value:int64):>int64 => value + 1
let decrement = (value:int64):>int64 => value - 1
const handlers = [@increment @decrement]
let main = ():>void => {
    let selected = handlers[0]
    return void
}
'''))

    assert (
        'const handlers:int64 = '
        '__static_words__(@increment @decrement)'
    ) in emitted
    assert 'let selected:<(value:int64):>int64> = __load_i64__(handlers)' in emitted
    assert '__static_alloca__(48)' not in emitted


def test_local_function_array_uses_typed_stack_data() -> None:
    emitted = codegen(SrcFile(None, '''
let increment = (value:int64):>int64 => value + 1
let decrement = (value:int64):>int64 => value - 1
let apply = ():>int64 => {
    let handlers = [@increment @decrement]
    let selected = handlers[0]
    return selected(41)
}
'''))

    assert 'let handlers:int64 = __alloca__(16)' in emitted
    assert '__store_i64__((@increment transmute int64) handlers)' in emitted
    assert '__store_i64__((@decrement transmute int64) handlers + 8)' in emitted
    assert 'let selected:<(value:int64):>int64> = __load_i64__(handlers)' in emitted
    assert '__alloca__(48)' not in emitted


def test_local_string_handle_array_uses_stack_data() -> None:
    emitted = codegen(SrcFile(None, '''
let read = ():>int64 => {
    let values:array<string> = ["a" "ok"]
    return values[1].length + 40
}
'''))

    assert 'let values:int64 = __alloca__(16)' in emitted
    assert '__store_i64__(__dewy_string_value_2 values)' in emitted
    assert '__store_i64__(__dewy_string_value_4 values + 8)' in emitted
    assert '__load_i64__(values + 8)' in emitted
    assert '__alloca__(48)' not in emitted


def test_module_const_based_bytes_use_raw_static_pointer() -> None:
    emitted = codegen(SrcFile(None, '''
const data:array<uint8> = 0q"02200002"
let main = ():>int64 => {
    if data.length =? 2 and data[0] =? 40 and data[1] =? 2 {
        return 42
    } else {
        return 1
    }
}
'''))

    assert 'const data:int64 = 0x"2802"' in emitted
    assert '__load_u8__(data)' in emitted
    assert '__load_u8__(data + 1)' in emitted
    assert '__static_alloca__(48)' not in emitted


@pytest.mark.parametrize(
    'source',
    [
        '''
let words:array<int64> = [10 20]
let main = ():>int64 => words[0]
''',
        '''
const words:array<uint32> = [10 20]
let main = ():>uint32 => words[0]
''',
    ],
)
def test_static_word_array_ambiguous_cases_keep_descriptors(source: str) -> None:
    emitted = codegen(SrcFile(None, source))

    assert '__static_words__(' not in emitted
    assert 'alloca__(48)' in emitted
    assert '__store_i64__(' in emitted


def test_transitive_local_array_bindings_receive_distinct_storage() -> None:
    emitted = codegen(SrcFile(None, '''
let read = ():>int64 => {
    let values = [20 22]
    let alias = values
    let transitive = alias
    transitive[0] = 40
    return alias[0] + values.length
}
'''))

    assert 'let values:int64 = __alloca__(16)' in emitted
    assert 'let alias:int64 = values' not in emitted
    assert 'let transitive:int64 = alias' not in emitted
    assert emitted.count('__alloca__(16)') == 3
    assert '__store_i64__(40 transitive)' in emitted
    assert 'return __load_i64__(alias) + 2' in emitted
    assert '__alloca__(48)' not in emitted


def test_nested_array_value_copy_materializes_recursive_storage() -> None:
    emitted = codegen(SrcFile(None, '''
let read = ():>int64 => {
    let original = [[1 2] [3 4]]
    let copy = original
    copy[0][0] = 9
    return original[0][0] + copy[0][0]
}
'''))

    assert 'let original:int64 = __alloca__(16)' in emitted
    assert 'let copy:int64 = __alloca__(16)' in emitted
    assert emitted.count('__alloca__(48)') == 4
    assert '__store_i64__(9 __load_i64__(__load_i64__(copy)))' in emitted


@pytest.mark.parametrize(
    ('source', 'expected_fragments'),
    [
        (
            '''
let read = ():>int64 => {
    let values = [20 22]
    let replacement = [40 2]
    values = replacement
    return values[1]
}
''',
            (
                'let values:int64 = __dewy_array_1',
                'let replacement:int64 = __dewy_array_3',
                'values = __dewy_array_5',
            ),
        ),
        (
            '''
let read = ():>int64 => {
    let values = [42 0]
    let box = [items = values]
    return box.items[0]
}
''',
            (
                'let values:int64 = __dewy_array_1',
                '__store_i64__(__dewy_array_3 __dewy_object_1)',
                '__load_i64__(__load_i64__(__load_i64__(box)))',
            ),
        ),
        (
            '''
let read = ():>uint8 => {
    let values:array<uint8> = 0x"2a00"
    values[0] = 42
    return values[0]
}
''',
            (
                'let values:int64 = __dewy_array_1',
                '__dewy_array_cow_data_',
                '__load_u8__(__load_i64__(values))',
            ),
        ),
    ],
)
def test_local_array_boundaries_keep_descriptors(
    source: str,
    expected_fragments: tuple[str, ...],
) -> None:
    emitted = codegen(SrcFile(None, source))

    assert 'alloca__(48)' in emitted
    assert 'let values:int64 = __alloca__(' not in emitted
    for fragment in expected_fragments:
        assert fragment in emitted


def test_static_words_is_available_as_a_direct_dewy_intrinsic() -> None:
    emitted = codegen(SrcFile(None, 'const data:int64 = __static_words__(40 2)'))

    assert 'data = __static_words__(40 2)' in emitted


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
@pytest.mark.parametrize(
    ('name', 'source'),
    [
        (
            'static_words',
            '''
const forty:int64 = 40
const words:array<int64> = [forty 2]
let main = ():>int64 => words[0] + words[1]
''',
        ),
        (
            'static_bytes',
            '''
const data:array<uint8> = 0x"2802"
let main = ():>int64 => {
    if data.length =? 2 and data[0] =? 40 and data[1] =? 2 {
        return 42
    } else {
        return 1
    }
}
''',
        ),
        (
            'static_functions',
            '''
let increment = (value:int64):>int64 => value + 1
let decrement = (value:int64):>int64 => value - 1
const handlers = [@increment @decrement]
let main = ():>int64 => {
    let selected = handlers[0]
    return increment(41)
}
''',
        ),
        (
            'local_functions',
            '''
let increment = (value:int64):>int64 => value + 1
let decrement = (value:int64):>int64 => value - 1
let main = ():>int64 => {
    let handlers = [@increment @decrement]
    let selected = handlers[0]
    return selected(41)
}
''',
        ),
        (
            'local_bools',
            '''
let main = ():>int64 => {
    let flags = [false true]
    flags[0] = true
    if flags[0] and flags[1] {
        return 42
    } else {
        return 1
    }
}
''',
        ),
        (
            'local_handles',
            '''
let main = ():>int64 => {
    let values:array<string> = ["a" "ok"]
    return values[1].length + 40
}
''',
        ),
        (
            'local_alias_call_adapter',
            '''
let mutate = (items:array<int64 length=2>):>int64 => {
    items[0] = 40
    return items[0] + items[1]
}
let main = ():>int64 => {
    let values = [0 2]
    let alias = values
    return mutate(alias)
}
''',
        ),
        (
            'static_words_call_adapter',
            '''
const words:array<int64> = [40 2]
let sum = (items:array<int64 length=2>):>int64 => items[0] + items[1]
let main = ():>int64 => sum(words)
''',
        ),
        (
            'static_words_mutating_call_adapter',
            '''
const words:array<int64> = [0 2]
let mutate = (items:array<int64 length=2>):>int64 => {
    items[0] = 40
    return items[0] + items[1]
}
let main = ():>int64 => mutate(words)
''',
        ),
        (
            'static_bytes_call_adapter',
            '''
const bytes:array<uint8> = 0x"2802"
let verify = (items:array<uint8 length=2>):>int64 => {
    if items[0] =? 40 and items[1] =? 2 { return 42 } else { return 1 }
}
let main = ():>int64 => verify(bytes)
''',
        ),
        (
            'static_bytes_mutating_fallback',
            '''
const bytes:array<uint8> = 0x"0002"
let mutate = (items:array<uint8 length=2>):>int64 => {
    items[0] = 40
    if items[0] =? 40 and items[1] =? 2 { return 42 } else { return 1 }
}
let main = ():>int64 => mutate(bytes)
''',
        ),
        (
            'overload_call_adapter',
            '''
let read_array = (items:array<int64 length=2>):>int64 =>
    items[0] + items[1]
let identity = (value:int64):>int64 => value
let selected = @read_array & @identity
let main = ():>int64 => {
    let values = [40 2]
    return selected(values)
}
''',
        ),
    ],
)
def test_static_array_representations_run(
    name: str,
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / f'{name}.udewy'
    path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)

    assert entry_point(path, []) == 42
