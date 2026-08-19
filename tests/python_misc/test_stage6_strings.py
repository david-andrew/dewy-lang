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


def _declarations(root: hir.Block) -> dict[str, hir.Declare]:
    return {
        item.name: item
        for item in root.items
        if isinstance(item, hir.Declare)
    }


def test_string_literals_keep_exact_types_until_contextualized() -> None:
    root = _check(
        'let exact = "café" '
        'let text:string = "café" '
        'let bytes:array<uint8> = "café" '
        'let scalars:array<uint32> = "café" '
        'let clusters:array<grapheme> = "café"'
    )
    declarations = _declarations(root)

    assert declarations['exact'].expr.type == ty.StringLiteralType('café')
    assert isinstance(declarations['text'].expr, hir.RepresentationCast)
    assert declarations['text'].expr.type == 'string'
    assert declarations['bytes'].expr.type == ty.ArrayType('uint8', 6)
    assert declarations['scalars'].expr.type == ty.ArrayType('uint32', 5)
    assert declarations['clusters'].expr.type == ty.ArrayType('grapheme', 4)


def test_contextual_uint8_literal_materializes_without_grapheme_metadata() -> None:
    emitted = codegen(SrcFile(None, '''
let read = ():>uint8 => {
    let bytes:array<uint8> = "café"
    return bytes[3]
}
'''))

    assert '__dewy_string_boundaries_' not in emitted
    assert '__dewy_string_value_' not in emitted
    assert '"\\x63\\x61\\x66\\xc3\\xa9"' in emitted
    assert '__store_i64__(5 __dewy_array_1 + 8)' in emitted


def test_char_is_the_one_grapheme_string_refinement() -> None:
    root = _check(
        'let composed:char = "é" '
        'let decomposed:char = "é" '
        'let family:grapheme = "👨‍👩‍👧‍👦"'
    )
    declarations = _declarations(root)
    assert all(
        isinstance(declaration.expr, hir.RepresentationCast)
        for declaration in declarations.values()
    )

    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check('let invalid:char = "ab"')


def test_unproven_integer_arrays_cannot_be_converted_to_strings() -> None:
    with pytest.raises(TypeCheckError, match='validity proof'):
        _check('let bytes:array<uint8> = [97] let text = bytes as string')
    with pytest.raises(TypeCheckError, match='validity proof'):
        _check('let scalars:array<uint32> = [97] let text = scalars as string')


def test_grapheme_array_to_string_remains_a_runtime_conversion() -> None:
    source = (
        "let parts:array<grapheme> = ['e' 'x'] "
        "parts[1] = '́' "
        'let text:string = parts as string'
    )
    root = _check(source)
    declaration = _declarations(root)['text']

    assert isinstance(declaration.expr, hir.RepresentationCast)
    assert isinstance(declaration.expr.expr, hir.ExpressedIdentifier)

    emitted = codegen(SrcFile(None, source))
    assert '__dewy_string_grapheme_count_' in emitted
    assert '__dewy_string_gcb_' in emitted


def test_transmute_rejects_string_array_reinterpretation() -> None:
    with pytest.raises(TypeCheckError, match='incompatible transmute'):
        _check('let bytes = "abc" transmute array<uint8>')


def test_strings_are_immutable_but_byte_views_are_mutable() -> None:
    with pytest.raises(UserError, match='immutable string'):
        _check('let text = "abc" text[0] = "x"')

    _check(
        'let text = "abc" '
        'let bytes:array<uint8> = text as array<uint8> '
        'bytes[0] = 120'
    )


def test_string_length_index_slice_and_equality_hir() -> None:
    root = _check(
        'let text = "café 👨‍👩‍👧‍👦 🇺🇸" '
        'let count = text.length '
        'let family = text[5] '
        'let prefix = text[[0..3]] '
        'let direct = text[3..7) '
        'let same = prefix =? "café"'
    )
    declarations = _declarations(root)

    assert declarations['count'].expr.type == ty.IntegerLiteralType(8)
    assert isinstance(declarations['family'].expr, hir.StringIndex)
    assert declarations['family'].expr.type == ty.StringType(1)
    assert isinstance(declarations['prefix'].expr, hir.StringSlice)
    assert declarations['prefix'].expr.type == ty.StringType(4)
    assert isinstance(declarations['direct'].expr, hir.StringSlice)
    assert declarations['direct'].expr.type == ty.StringType(4)
    assert declarations['direct'].expr.range.bounds == '[)'
    assert isinstance(declarations['same'].expr, hir.StringEqual)


def test_interpolated_string_preserves_chunks_and_checked_fields() -> None:
    source = '''
let index:int64 = 3
let value = "é"
let rendered = "{index}: {value}"
'''
    root = _check(source)
    rendered = _declarations(root)['rendered'].expr

    assert isinstance(rendered, hir.InterpolatedString)
    assert len(rendered.parts) == 3
    assert isinstance(rendered.parts[0], hir.ExpressedIdentifier)
    assert isinstance(rendered.parts[1], hir.String)
    assert rendered.parts[1].content == ': '
    assert isinstance(rendered.parts[2], hir.ExpressedIdentifier)

    with pytest.raises(
        NotImplementedYet,
        match='materializing an interpolated string outside print or printl',
    ):
        codegen(SrcFile(None, source))


def test_character_ranges_default_to_graphemes_and_skip_surrogates() -> None:
    root = _check(
        "loop c in 'a'..'z' { let one:grapheme = c } "
        "loop scalar in '\ud7ff'..'\ue000' { let one:char = scalar }"
    )
    loops = [
        item
        for item in root.items
        if isinstance(item, hir.Flow)
    ]
    assert len(loops) == 2
    for loop in loops:
        condition = loop.arms[0].condition
        assert isinstance(condition, hir.IteratorExpression)
        assert condition.target.type == ty.StringType(1)
    surrogate_gap = loops[1].arms[0].condition
    assert isinstance(surrogate_gap, hir.IteratorExpression)
    assert surrogate_gap.count == 2


def test_explicit_uint32_range_context_materializes_scalar_endpoints() -> None:
    root = _check("let letters:range<uint32> = 'a'..'z'")
    declaration = _declarations(root)['letters']
    assert isinstance(declaration.expr, hir.Range)
    assert declaration.expr.type == ty.TypeParameterize('range', ['uint32'])
    assert isinstance(declaration.expr.left, hir.Integer)
    assert declaration.expr.left.value == ord('a')
    assert isinstance(declaration.expr.right, hir.Integer)
    assert declaration.expr.right.value == ord('z')


def test_multi_scalar_grapheme_range_iteration_is_rejected() -> None:
    with pytest.raises(UserError, match='single-scalar graphemes'):
        _check("loop value in 'é'..'f' { void }")


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
def test_unicode_strings_compile_and_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = '''
let main = ():>int64 => {
    let text = "café 👨‍👩‍👧‍👦 🇺🇸"
    let family = text[5]
    let bytes:array<uint8> = text as array<uint8>
    bytes[0] = 120
    let untouched:array<uint8> = text as array<uint8>
    let direct:array<uint8> = "abc"
    direct[0] = 120
    let fresh:array<uint8> = "abc"
    let scalars:array<uint32> = text as array<uint32>
    if family.length =? 1
        and untouched[0] =? 99
        and direct[0] =? 120
        and fresh[0] =? 97
        and scalars[3] =? 233 {
        return 42
    } else {
        return 1
    }
}
'''
    path = tmp_path / 'unicode_strings.udewy'
    path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(path, []) == 42


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
def test_string_slices_use_grapheme_bounds_and_exact_equality(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = '''
let main = ():>int64 => {
    let text = "abcdef"
    if text[[..2]] =? "abc"
        and text[[2..]] =? "cdef"
        and text[(1..4)] =? "cd"
        and text[[1..4)] =? "bcd"
        and text[(1..4]] =? "cde"
        and "é" not=? "é" {
        return 42
    } else {
        return 1
    }
}
'''
    path = tmp_path / 'string_slices.udewy'
    path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(path, []) == 42


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
def test_hero_core_iterates_graphemes_and_streams_interpolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source = '''
text = "café 👨‍👩‍👧‍👦 🍀"

loop i in 0.. and c in text
    if c not =? ' ' {
        printl"{i}: {c}"
    }
'''
    path = tmp_path / 'hero_core.udewy'
    path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)

    assert entry_point(path, []) == 0
    assert capfd.readouterr().out == (
        '0: c\n'
        '1: a\n'
        '2: f\n'
        '3: é\n'
        '5: 👨‍👩‍👧‍👦\n'
        '7: 🍀\n'
    )
