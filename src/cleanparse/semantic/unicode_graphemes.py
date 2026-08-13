"""Unicode scalar and extended grapheme cluster operations."""

from bisect import bisect_right

from src.cleanparse.semantic.unicode_data import (
    EXTENDED_PICTOGRAPHIC_RANGES,
    GRAPHEME_BREAK_RANGES,
    INDIC_CONJUNCT_BREAK_RANGES,
    UNICODE_VERSION as UNICODE_VERSION,
)


UNICODE_SCALAR_COUNT = 0x110000 - 0x800
MAX_UNICODE_SCALAR_ORDINAL = UNICODE_SCALAR_COUNT - 1

_GRAPHEME_BREAK_STARTS = tuple(
    start for start, _, _ in GRAPHEME_BREAK_RANGES
)
_EXTENDED_PICTOGRAPHIC_STARTS = tuple(
    start for start, _, _ in EXTENDED_PICTOGRAPHIC_RANGES
)
_INDIC_CONJUNCT_BREAK_STARTS = tuple(
    start for start, _, _ in INDIC_CONJUNCT_BREAK_RANGES
)
_CONTROL_PROPERTIES = frozenset({'Control', 'CR', 'LF'})
_INDIC_LINKING_PROPERTIES = frozenset({'Extend', 'Linker'})


def is_unicode_scalar(value: int) -> bool:
    """Return whether value is a Unicode scalar value."""
    return 0 <= value <= 0x10FFFF and not 0xD800 <= value <= 0xDFFF


def validate_unicode_scalar(value: int) -> int:
    """Return value, raising ValueError if it is not a Unicode scalar."""
    if not is_unicode_scalar(value):
        raise ValueError(f'not a Unicode scalar value: {value:#x}')
    return value


def unicode_scalars(text: str) -> tuple[int, ...]:
    """Return the Unicode scalar values in text."""
    scalars = tuple(map(ord, text))
    for scalar in scalars:
        validate_unicode_scalar(scalar)
    return scalars


def utf8_bytes(text: str) -> bytes:
    """Return the canonical UTF-8 encoding of scalar-only text."""
    unicode_scalars(text)
    return text.encode('utf-8')


def unicode_scalar_ordinal(scalar: int) -> int:
    """Map a scalar to its dense ordinal, omitting the surrogate range."""
    validate_unicode_scalar(scalar)
    return scalar if scalar < 0xD800 else scalar - 0x800


def unicode_scalar_from_ordinal(ordinal: int) -> int:
    """Map a dense Unicode scalar ordinal back to a scalar value."""
    if not 0 <= ordinal < UNICODE_SCALAR_COUNT:
        raise ValueError(f'not a Unicode scalar ordinal: {ordinal}')
    return ordinal if ordinal < 0xD800 else ordinal + 0x800


def _range_property(
    scalar: int,
    starts: tuple[int, ...],
    ranges: tuple[tuple[int, int, str], ...],
    default: str,
) -> str:
    index = bisect_right(starts, scalar) - 1
    if index >= 0:
        _, end, value = ranges[index]
        if scalar <= end:
            return value
    return default


def _grapheme_break_property(scalar: int) -> str:
    return _range_property(
        scalar,
        _GRAPHEME_BREAK_STARTS,
        GRAPHEME_BREAK_RANGES,
        'Other',
    )


def _indic_conjunct_break_property(scalar: int) -> str:
    return _range_property(
        scalar,
        _INDIC_CONJUNCT_BREAK_STARTS,
        INDIC_CONJUNCT_BREAK_RANGES,
        'None',
    )


def _is_extended_pictographic(scalar: int) -> bool:
    return (
        _range_property(
            scalar,
            _EXTENDED_PICTOGRAPHIC_STARTS,
            EXTENDED_PICTOGRAPHIC_RANGES,
            '',
        )
        == 'Extended_Pictographic'
    )


def _has_grapheme_break(
    index: int,
    grapheme_break: tuple[str, ...],
    indic_conjunct_break: tuple[str, ...],
    extended_pictographic: tuple[bool, ...],
) -> bool:
    left = grapheme_break[index - 1]
    right = grapheme_break[index]

    if left == 'CR' and right == 'LF':
        return False
    if left in _CONTROL_PROPERTIES or right in _CONTROL_PROPERTIES:
        return True
    if left == 'L' and right in {'L', 'V', 'LV', 'LVT'}:
        return False
    if left in {'LV', 'V'} and right in {'V', 'T'}:
        return False
    if left in {'LVT', 'T'} and right == 'T':
        return False
    if right in {'Extend', 'ZWJ'}:
        return False
    if right == 'SpacingMark':
        return False
    if left == 'Prepend':
        return False

    if indic_conjunct_break[index] == 'Consonant':
        cursor = index - 1
        has_linker = False
        while (
            cursor >= 0
            and indic_conjunct_break[cursor] in _INDIC_LINKING_PROPERTIES
        ):
            has_linker |= indic_conjunct_break[cursor] == 'Linker'
            cursor -= 1
        if (
            has_linker
            and cursor >= 0
            and indic_conjunct_break[cursor] == 'Consonant'
        ):
            return False

    if extended_pictographic[index] and left == 'ZWJ':
        cursor = index - 2
        while cursor >= 0 and grapheme_break[cursor] == 'Extend':
            cursor -= 1
        if cursor >= 0 and extended_pictographic[cursor]:
            return False

    if left == 'Regional_Indicator' and right == 'Regional_Indicator':
        regional_indicators = 1
        cursor = index - 2
        while (
            cursor >= 0
            and grapheme_break[cursor] == 'Regional_Indicator'
        ):
            regional_indicators += 1
            cursor -= 1
        if regional_indicators % 2 == 1:
            return False

    return True


def _grapheme_boundaries(text: str) -> tuple[int, ...]:
    scalars = unicode_scalars(text)
    grapheme_break = tuple(map(_grapheme_break_property, scalars))
    indic_conjunct_break = tuple(
        map(_indic_conjunct_break_property, scalars)
    )
    extended_pictographic = tuple(map(_is_extended_pictographic, scalars))

    boundaries = [0]
    boundaries.extend(
        index
        for index in range(1, len(scalars))
        if _has_grapheme_break(
            index,
            grapheme_break,
            indic_conjunct_break,
            extended_pictographic,
        )
    )
    if scalars:
        boundaries.append(len(scalars))
    return tuple(boundaries)


def grapheme_boundary_byte_offsets(text: str) -> tuple[int, ...]:
    """Return UTF-8 byte offsets at every extended grapheme boundary."""
    boundaries = _grapheme_boundaries(text)
    byte_offsets = [0]
    for character in text:
        byte_offsets.append(
            byte_offsets[-1] + len(character.encode('utf-8'))
        )
    return tuple(byte_offsets[index] for index in boundaries)


def graphemes(text: str) -> tuple[str, ...]:
    """Return text split into UAX #29 extended grapheme clusters."""
    boundaries = _grapheme_boundaries(text)
    return tuple(
        text[start:end]
        for start, end in zip(boundaries, boundaries[1:])
    )


def grapheme_count(text: str) -> int:
    """Return the number of extended grapheme clusters in text."""
    return len(_grapheme_boundaries(text)) - 1
