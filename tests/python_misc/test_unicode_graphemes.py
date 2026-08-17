from pathlib import Path

import pytest

from src.cleanparse.semantic.unicode.graphemes import (
    MAX_UNICODE_SCALAR_ORDINAL,
    UNICODE_SCALAR_COUNT,
    UNICODE_VERSION,
    grapheme_boundary_byte_offsets,
    grapheme_count,
    graphemes,
    is_unicode_scalar,
    unicode_scalar_from_ordinal,
    unicode_scalar_ordinal,
    unicode_scalars,
    utf8_bytes,
    validate_unicode_scalar,
)

HERE = Path(__file__).parent


def test_unicode_version_is_pinned() -> None:
    assert UNICODE_VERSION == '16.0.0'


def test_unicode_scalar_validation_and_conversion() -> None:
    assert is_unicode_scalar(0)
    assert is_unicode_scalar(0xD7FF)
    assert is_unicode_scalar(0xE000)
    assert is_unicode_scalar(0x10FFFF)
    assert not is_unicode_scalar(-1)
    assert not is_unicode_scalar(0xD800)
    assert not is_unicode_scalar(0xDFFF)
    assert not is_unicode_scalar(0x110000)
    assert validate_unicode_scalar(0x1F642) == 0x1F642

    with pytest.raises(ValueError):
        validate_unicode_scalar(0xD800)


def test_scalar_ordinals_skip_surrogates() -> None:
    assert UNICODE_SCALAR_COUNT == 0x10F800
    assert MAX_UNICODE_SCALAR_ORDINAL == 0x10F7FF
    assert unicode_scalar_ordinal(0xD7FF) == 0xD7FF
    assert unicode_scalar_ordinal(0xE000) == 0xD800
    assert unicode_scalar_from_ordinal(0xD7FF) == 0xD7FF
    assert unicode_scalar_from_ordinal(0xD800) == 0xE000
    assert unicode_scalar_from_ordinal(MAX_UNICODE_SCALAR_ORDINAL) == 0x10FFFF

    for scalar in (0, 0x61, 0xD7FF, 0xE000, 0x1F642, 0x10FFFF):
        assert unicode_scalar_from_ordinal(
            unicode_scalar_ordinal(scalar)
        ) == scalar

    with pytest.raises(ValueError):
        unicode_scalar_from_ordinal(UNICODE_SCALAR_COUNT)


def test_scalar_tuple_and_utf8_encoding() -> None:
    text = 'café🙂'
    assert unicode_scalars(text) == (0x63, 0x61, 0x66, 0xE9, 0x1F642)
    assert utf8_bytes(text) == b'caf\xc3\xa9\xf0\x9f\x99\x82'

    with pytest.raises(ValueError):
        unicode_scalars('\ud800')
    with pytest.raises(ValueError):
        utf8_bytes('\ud800')


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('café', ('c', 'a', 'f', 'é')),
        ('cafe\u0301', ('c', 'a', 'f', 'e\u0301')),
        ('👨\u200d👩\u200d👧\u200d👦', ('👨\u200d👩\u200d👧\u200d👦',)),
        ('👍🏽', ('👍🏽',)),
        ('🇺🇸🇨🇦🇯', ('🇺🇸', '🇨🇦', '🇯')),
        ('\u1100\u1161\u11a8', ('\u1100\u1161\u11a8',)),
        ('\uac00\u11a8', ('\uac00\u11a8',)),
        ('\uac01\u11a8', ('\uac01\u11a8',)),
        ('का', ('का',)),
        ('\u0600A', ('\u0600A',)),
        ('a\r\nb\x00c', ('a', '\r\n', 'b', '\x00', 'c')),
        ('क्क', ('क्क',)),
        ('क्\u200dक', ('क्\u200dक',)),
    ],
)
def test_extended_grapheme_clusters(
    text: str,
    expected: tuple[str, ...],
) -> None:
    assert graphemes(text) == expected
    assert grapheme_count(text) == len(expected)


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('\r\n', ('\r\n',)),
        ('\r\u0308', ('\r', '\u0308')),
        ('a\u0308b', ('a\u0308', 'b')),
        ('\u0600a', ('\u0600a',)),
        ('\u1100\u1160\u11a8', ('\u1100\u1160\u11a8',)),
        ('🇦🇧🇨', ('🇦🇧', '🇨')),
        ('👩\u0308\u200d👩', ('👩\u0308\u200d👩',)),
    ],
)
def test_selected_uax_29_conformance_cases(
    text: str,
    expected: tuple[str, ...],
) -> None:
    assert graphemes(text) == expected


def test_unicode_uax_29_grapheme_break_conformance() -> None:
    fixture = HERE.parent / 'data' / 'GraphemeBreakTest-16.0.0.txt'
    for line_number, raw_line in enumerate(fixture.read_text().splitlines(), 1):
        case = raw_line.split('#', 1)[0].strip()
        if not case:
            continue

        tokens = case.split()
        text = ''
        expected: list[str] = []
        cluster = ''
        for marker, scalar in zip(tokens[:-1:2], tokens[1::2], strict=True):
            if marker == '÷' and cluster:
                expected.append(cluster)
                cluster = ''
            character = chr(int(scalar, 16))
            text += character
            cluster += character
        if cluster:
            expected.append(cluster)

        assert tokens[-1] == '÷'
        assert graphemes(text) == tuple(expected), f'fixture line {line_number}'


def test_grapheme_boundary_utf8_byte_offsets() -> None:
    assert grapheme_boundary_byte_offsets('') == (0,)
    assert grapheme_boundary_byte_offsets('cafe\u0301🙂') == (
        0,
        1,
        2,
        3,
        6,
        10,
    )
    family = '👨\u200d👩\u200d👧\u200d👦'
    assert grapheme_boundary_byte_offsets(family) == (0, 25)
