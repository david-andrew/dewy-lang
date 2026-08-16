from pathlib import Path
from shutil import which

import pytest

from src.cleanparse.backend.udewy import codegen
from src.cleanparse.reporting import SrcFile
from src.cleanparse.semantic import check, hir, ty
from src.cleanparse.semantic.errors import TypeCheckError, UserError
from src.cleanparse.semantic.hir_display import hir_to_dewy, type_to_dewy
from udewy.frontend import entry_point


def _check(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root


def _declarations(root: hir.Block) -> dict[str, hir.Declare]:
    return {
        item.name: item
        for item in root.items
        if isinstance(item, hir.Declare)
    }


@pytest.mark.parametrize(
    ('literal', 'expected'),
    [
        ('0b"1"', b'\x80'),
        ('0q"123"', b'\x6c'),
        ('0o"17"', b'\x3c'),
        ('0x"abc"', b'\xab\xc0'),
        ('0u"0v"', b'\x07\xc0'),
        ('0g"A_=="', b'\x93\xf0'),
        ('0g"-_"', b'\xfb\xf0'),
    ],
)
def test_power_of_two_based_strings_pack_msb_first(
    literal: str,
    expected: bytes,
) -> None:
    expression = _declarations(_check(f'let data = {literal}'))['data'].expr

    assert isinstance(expression, hir.BasedString)
    assert expression.content == expected
    assert expression.type == ty.BinaryLiteralType(expected)
    assert hir_to_dewy(expression) == literal


@pytest.mark.parametrize('prefix', ['0t', '0s', '0d', '0z', '0r'])
def test_non_power_of_two_based_strings_are_reserved(prefix: str) -> None:
    with pytest.raises(UserError, match='reserved for future dense packing'):
        _check(f'let data = {prefix}"1"')


def test_base64_padding_must_be_trailing() -> None:
    with pytest.raises(UserError, match='padding'):
        _check('let data = 0g"A=A"')


def test_based_strings_materialize_only_as_exact_byte_arrays() -> None:
    root = _check(
        'let exact = 0x"abc" '
        'let contextual:array<uint8> = 0x"abc" '
        'let explicit = 0x"abc" as array<uint8>'
    )
    declarations = _declarations(root)

    assert declarations['exact'].expr.type == ty.BinaryLiteralType(b'\xab\xc0')
    for name in ('contextual', 'explicit'):
        expression = declarations[name].expr
        assert isinstance(expression, hir.RepresentationCast)
        assert expression.type == ty.ArrayType('uint8', 2)

    with pytest.raises(TypeCheckError, match='array length mismatch|type mismatch'):
        _check('let data:array<uint8 length=3> = 0x"abc"')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check('let data:array<uint16> = 0x"abc"')


def test_based_strings_contextually_materialize_for_calls() -> None:
    root = _check(
        'let size = (data:array<uint8>):>int64 => data.length '
        'let count = size(0x"abcd")'
    )
    call = _declarations(root)['count'].expr

    assert isinstance(call, hir.FunctionCall)
    assert isinstance(call.pos_args[0], hir.RepresentationCast)
    assert call.pos_args[0].type == ty.ArrayType('uint8', 2)


@pytest.mark.parametrize('target', ['string', 'grapheme', 'char'])
def test_based_strings_reject_text_conversions(target: str) -> None:
    with pytest.raises(TypeCheckError, match='binary data is not Unicode text'):
        _check(f'let text = 0x"61" as {target}')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check(f'let text:{target} = 0x"61"')


def test_based_strings_reject_transmute_to_arrays() -> None:
    with pytest.raises(TypeCheckError, match='incompatible transmute'):
        _check('let data = 0x"abcd" transmute array<uint8 length=2>')


def test_based_string_array_inference_and_length_propagation() -> None:
    root = _check(
        'let rows = [0x"12" 0b"00110100"] '
        'let data = 0x"abc" '
        'let count = data.length '
        'let byte = data[1]'
    )
    declarations = _declarations(root)

    rows = declarations['rows'].expr
    assert rows.type == ty.ArrayType(ty.ArrayType('uint8', 1), 2)
    assert all(isinstance(item, hir.RepresentationCast) for item in rows.items)
    assert declarations['count'].expr.type == ty.IntegerLiteralType(2)
    assert declarations['byte'].expr.type == 'uint8'

    with pytest.raises(TypeCheckError, match='not homogeneous'):
        _check('let rows = [0x"12" 0x"1234"]')


def test_binary_literal_type_implication_and_substitution() -> None:
    system = ty.TypeSystem()
    exact = ty.BinaryLiteralType(b'\x12\x30')

    assert system.is_subtype(exact, ty.ArrayType('uint8', 2))
    assert system.is_subtype(exact, ty.ArrayType('uint8'))
    assert not system.is_subtype(exact, ty.ArrayType('uint8', 3))
    assert not system.is_subtype(exact, 'string')
    assert ty.substitute_type(exact, {'T': 'uint8'}) is exact
    assert type_to_dewy(exact) == '0x"1230"'


def test_codegen_uses_canonical_static_pointer_for_exact_binary() -> None:
    emitted = codegen(SrcFile(None, '''
let read = ():>uint8 => {
    const data = 0g"-_=="
    let count = data.length
    return data[count - 1]
}
'''))

    assert 'const data:int64 = 0x"fbf0"' in emitted
    assert 'return __load_u8__(data + 1)' in emitted
    assert '0g"' not in emitted
    assert '__alloca__(48)' not in emitted
    assert '__dewy_string_' not in emitted


def test_codegen_materializes_borrowed_static_byte_array_descriptor() -> None:
    emitted = codegen(SrcFile(None, '''
let mutate = ():>uint8 => {
    let exact = 0q"01000200"
    let data:array<uint8> = exact as array<uint8>
    data[0] = 40
    return data[0]
}
'''))

    assert '__alloca__(48)' in emitted
    assert 'let exact:int64 = 0x"1020"' in emitted
    assert '__store_i64__(exact __dewy_array_1)' in emitted
    assert '__store_i64__(2 __dewy_array_1 + 8)' in emitted
    assert '__store_i64__(1 __dewy_array_1 + 24)' in emitted
    assert '__store_i64__(2 __dewy_array_1 + 32)' in emitted
    assert '__dewy_array_cow_data_' in emitted
    assert '__dewy_string_' not in emitted


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
def test_mutable_based_byte_array_copies_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = '''
let main = ():>int64 => {
    let data:array<uint8> = 0x"0102"
    data[0] = 40
    if data[0] =? 40 and data[1] =? 2 {
        return 42
    } else {
        return 1
    }
}
'''
    path = tmp_path / 'based_byte_array.udewy'
    path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)

    assert entry_point(path, []) == 42
