from pathlib import Path
from shutil import which

import pytest

from src.cleanparse.backend.udewy import codegen
from src.cleanparse.backend.udewy.lower import ArrayRepresentation, ArrayUse, _Lowerer
from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic import check, hir
from src.cleanparse.semantic.errors import UserError
from udewy.frontend import entry_point


def _classify_array_representations(
    source: str,
) -> tuple[dict[str, ArrayRepresentation], dict[str, set[ArrayUse]]]:
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
        binding_id: binding.name
        for binding_id, binding in lowerer.binding_by_semantic_id.items()
    }
    representations = {
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


@pytest.mark.parametrize(
    ('name', 'source'),
    [
        (
            'values',
            '''
let read = ():>int64 => {
    let values = [20 22]
    let alias = values
    return alias[1]
}
''',
        ),
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
let first = (items:array<int64 length=2>):>int64 => items[0]
let read = ():>int64 => {
    let values = [42 0]
    return first(values)
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
const handlers = [increment decrement]
let main = ():>void => {
    let selected = handlers[0]
    return void
}
'''))

    assert (
        'const handlers:int64 = '
        '__static_words__(increment decrement)'
    ) in emitted
    assert 'let selected:<(value:int64):>int64> = __load_i64__(handlers)' in emitted
    assert '__static_alloca__(48)' not in emitted


def test_local_function_array_uses_typed_stack_data() -> None:
    emitted = codegen(SrcFile(None, '''
let increment = (value:int64):>int64 => value + 1
let decrement = (value:int64):>int64 => value - 1
let apply = ():>int64 => {
    let handlers = [increment decrement]
    let selected = handlers[0]
    return selected(41)
}
'''))

    assert 'let handlers:int64 = __alloca__(16)' in emitted
    assert '__store_i64__((increment transmute int64) handlers)' in emitted
    assert '__store_i64__((decrement transmute int64) handlers + 8)' in emitted
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
        '''
const words:array<int64> = [10 20]
let first = (items:array<int64 length=2>):>int64 => items[0]
let main = ():>int64 => first(words)
''',
    ],
)
def test_static_word_array_ambiguous_cases_keep_descriptors(source: str) -> None:
    emitted = codegen(SrcFile(None, source))

    assert '__static_words__(' not in emitted
    assert 'alloca__(48)' in emitted
    assert '__store_i64__(' in emitted


@pytest.mark.parametrize(
    ('source', 'expected_fragments'),
    [
        (
            '''
let read = ():>int64 => {
    let values = [20 22]
    let alias = values
    return alias[1]
}
''',
            (
                'let values:int64 = __dewy_array_1',
                'let alias:int64 = values',
                '__load_i64__(__load_i64__(alias) + 8)',
            ),
        ),
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
                'values = replacement',
            ),
        ),
        (
            '''
let first = (items:array<int64 length=2>):>int64 => items[0]
let read = ():>int64 => {
    let values = [42 0]
    return first(values)
}
''',
            (
                'let values:int64 = __dewy_array_1',
                'return first(values)',
                '__load_i64__(__load_i64__(items))',
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
                '__store_i64__(values __dewy_object_1)',
                '__load_i64__(__load_i64__(__load_i64__(box)))',
            ),
        ),
        (
            '''
let first = (items:array<int64 length=2>):>int64 => {
    let values = items
    return values[0]
}
const source = [42 0]
let read = ():>int64 => first(source)
''',
            (
                'let values:int64 = items',
                '__load_i64__(__load_i64__(values))',
                'return first(source)',
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


def test_static_words_is_not_a_dewy_builtin() -> None:
    with pytest.raises(UserError, match='undefined identifier `__static_words__`'):
        codegen(SrcFile(None, 'let data = __static_words__(1)'))


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
const handlers = [increment decrement]
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
    let handlers = [increment decrement]
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
