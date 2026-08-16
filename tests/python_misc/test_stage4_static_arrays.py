from pathlib import Path
from shutil import which

import pytest

from src.cleanparse.backend.udewy import codegen
from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic.errors import UserError
from udewy.frontend import entry_point


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
let read = ():>int64 => {
    const words:array<int64> = [10 20]
    return words[0]
}
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
