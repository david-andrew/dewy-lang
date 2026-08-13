"""Compact Unicode 16.0.0 tables for emitted grapheme segmentation."""

from ...semantic.unicode_data import (
    EXTENDED_PICTOGRAPHIC_RANGES,
    GRAPHEME_BREAK_RANGES,
    INDIC_CONJUNCT_BREAK_RANGES,
)


TABLE_RECORD_BYTES = 9
TABLE_BYTE_OFFSET = 33

GCB_OTHER = 0
GCB_CR = 1
GCB_LF = 2
GCB_CONTROL = 3
GCB_L = 4
GCB_V = 5
GCB_T = 6
GCB_LV = 7
GCB_LVT = 8
GCB_EXTEND = 9
GCB_ZWJ = 10
GCB_SPACING_MARK = 11
GCB_PREPEND = 12
GCB_REGIONAL_INDICATOR = 13

INCB_NONE = 0
INCB_CONSONANT = 1
INCB_EXTEND = 2
INCB_LINKER = 3

_GCB_VALUES = {
    'CR': GCB_CR,
    'LF': GCB_LF,
    'Control': GCB_CONTROL,
    'L': GCB_L,
    'V': GCB_V,
    'T': GCB_T,
    'LV': GCB_LV,
    'LVT': GCB_LVT,
    'Extend': GCB_EXTEND,
    'ZWJ': GCB_ZWJ,
    'SpacingMark': GCB_SPACING_MARK,
    'Prepend': GCB_PREPEND,
    'Regional_Indicator': GCB_REGIONAL_INDICATOR,
}
_INCB_VALUES = {
    'Consonant': INCB_CONSONANT,
    'Extend': INCB_EXTEND,
    'Linker': INCB_LINKER,
}


def _encode_scalar(value: int) -> str:
    return ''.join(
        chr(TABLE_BYTE_OFFSET + (value >> shift & 0x3F))
        for shift in (18, 12, 6, 0)
    )


def _encode_ranges(
    ranges: tuple[tuple[int, int, str], ...],
    values: dict[str, int],
) -> str:
    return ''.join(
        _encode_scalar(start)
        + _encode_scalar(end)
        + chr(TABLE_BYTE_OFFSET + values[property_])
        for start, end, property_ in ranges
    )


GRAPHEME_BREAK_TABLE = _encode_ranges(GRAPHEME_BREAK_RANGES, _GCB_VALUES)
EXTENDED_PICTOGRAPHIC_TABLE = _encode_ranges(
    EXTENDED_PICTOGRAPHIC_RANGES,
    {'Extended_Pictographic': 1},
)
INDIC_CONJUNCT_BREAK_TABLE = _encode_ranges(
    INDIC_CONJUNCT_BREAK_RANGES,
    _INCB_VALUES,
)

GRAPHEME_BREAK_RECORDS = len(GRAPHEME_BREAK_RANGES)
EXTENDED_PICTOGRAPHIC_RECORDS = len(EXTENDED_PICTOGRAPHIC_RANGES)
INDIC_CONJUNCT_BREAK_RECORDS = len(INDIC_CONJUNCT_BREAK_RANGES)
