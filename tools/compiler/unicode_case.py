"""Pack Unicode's default full case mappings into lib/std/unicode/case_mapping.bin.

The mappings are those of Python's str.lower and str.upper (UnicodeData plus the
unconditional SpecialCasing entries), read from the Unicode tables built into the running
Python, so the generator needs no network. The context-sensitive final sigma is not in the
table: `lower` needs the Cased and Case_Ignorable properties, also packed here.

Layout (little-endian). First the direct section: for each code point from 0x80 to 0x4FF, a 16-bit
signed difference to its lower-case mapping, then the same for upper case; 0x8000 where the mapping
is not one code point of two UTF-8 bytes (or, for lower case, is the context-sensitive capital sigma).
Then the general part, in 32-bit words: the record counts of four sections (lower, upper, cased,
ignorable), the byte offsets in the file where those sections and then the blob start, the sections'
two-word records, then the blob of bytes. A character's key is its UTF-8 bytes as
one number, first byte highest: keys sort as code points do. A lower or upper record is a key and
the mapping's UTF-8 bytes in the blob: their offset * 16 + their count. A cased or ignorable record
is the first and last key of a range of characters.

Run with --check to verify the committed file. The check is skipped (exit 0, with a note)
on a Python whose Unicode version is not the pinned one.
"""
from __future__ import annotations

import argparse
import struct
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'lib/std/unicode/case_mapping.bin'
UNICODE_VERSION = '17.0.0'
SCALARS = 0x110000
DIRECT_FIRST, DIRECT_END = 0x80, 0x500
SURROGATES = range(0xD800, 0xE000)


def _scalars():
    return (c for c in range(SCALARS) if c not in SURROGATES)


def _key(c: int) -> int:
    return int.from_bytes(chr(c).encode(), 'big')


def _mappings(blob: bytearray, lower: bool) -> list[tuple[int, int]]:
    """Records (key, offset * 16 + count) of every character that has another case."""
    records = []
    seen: dict[bytes, int] = {}
    for c in _scalars():
        text = chr(c).lower() if lower else chr(c).upper()
        if text == chr(c):
            continue
        data = text.encode()
        assert len(data) < 16
        if data not in seen:
            seen[data] = len(blob)
            blob.extend(data)
        records.append((_key(c), seen[data] << 4 | len(data)))
    return sorted(records)


def _ranges(members: list[int]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for c in members:
        if out and out[-1][1] == c - 1:
            out[-1][1] = c
        else:
            out.append([c, c])
    return [(_key(first), _key(last)) for first, last in out]


def _properties() -> tuple[list[int], list[int]]:
    """Cased and Case_Ignorable as Python's final-sigma rule sees them.

    A character that is both counts as ignorable only, as the rule tests that first."""
    cased, ignorable = [], []
    for c in _scalars():
        ch = chr(c)
        if ('A' + 'Σ' + ch).lower()[1] == 'σ':
            cased.append(c)  # after the sigma: a cased letter makes it non-final
        elif ('A' + ch + 'Σ').lower().endswith('ς') and not ('1' + ch + 'Σ').lower().endswith('ς'):
            ignorable.append(c)  # between a cased letter and the sigma: skipped
    return cased, ignorable


def _direct(lower: bool) -> list[int]:
    out = []
    for c in range(DIRECT_FIRST, DIRECT_END):
        text = chr(c).lower() if lower else chr(c).upper()
        if (lower and c == 0x3A3) or len(text) != 1 or not 0x80 <= ord(text) <= 0x7FF:
            out.append(0x8000)
        else:
            out.append((ord(text) - c) & 0xFFFF)
    return out


def pack() -> bytes:
    blob = bytearray()
    sections = [_mappings(blob, True), _mappings(blob, False)]
    cased, ignorable = _properties()
    sections += [_ranges(cased), _ranges(ignorable)]
    direct = _direct(True) + _direct(False)
    start = 2 * len(direct) + 36
    starts = []
    for section in sections:
        starts.append(start)
        start += 8 * len(section)
    words = [len(section) for section in sections] + starts + [start]
    for section in sections:
        for record in section:
            words += record
    return struct.pack(f'<{len(direct)}H', *direct) + struct.pack(f'<{len(words)}I', *words) + bytes(blob)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if unicodedata.unidata_version != UNICODE_VERSION:
        if args.check:
            print(f'skipped: Python has Unicode {unicodedata.unidata_version}, the table is {UNICODE_VERSION}')
            sys.exit(0)
        parser.error(f'needs a Python with Unicode {UNICODE_VERSION} (this one has {unicodedata.unidata_version})')
    data = pack()
    if args.check:
        if TARGET.read_bytes() != data:
            parser.error('case_mapping.bin differs from the Unicode tables; regenerate it')
    else:
        TARGET.write_bytes(data)
    print(f'{len(data)} bytes')
