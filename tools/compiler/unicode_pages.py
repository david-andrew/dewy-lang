"""Pack the pinned Unicode 16 property ranges into deduplicated 256-codepoint pages.

No downloads or Unicode-version changes. Normal builds embed the committed file.
Run with --check to verify it, or without arguments after updating the source tables.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'lib/std/unicode'
SCALARS = 0x110000
PAGE_SIZE = 256
TABLES = (('grapheme_break.bin', 0, 15),
          ('indic_conjunct_break.bin', 4, 3),
          ('extended_pictographic.bin', 6, 1))


def pack(directory: Path = DIRECTORY) -> bytes:
    values = bytearray(SCALARS)
    for name, shift, maximum in TABLES:
        data = (directory / name).read_bytes()
        if len(data) % 9:
            raise ValueError(f'{name}: incomplete range record')
        previous = -1
        for start, end, value in struct.iter_unpack('<IIB', data):
            if not previous < start <= end < SCALARS or not 0 <= value <= maximum:
                raise ValueError(f'{name}: invalid or overlapping property range')
            for scalar in range(start, end + 1):
                values[scalar] |= value << shift
            previous = end
    pages = {}
    indices = bytearray()
    payload = bytearray()
    for start in range(0, SCALARS, PAGE_SIZE):
        page = bytes(values[start:start + PAGE_SIZE])
        if page not in pages:
            pages[page] = len(pages)
            payload.extend(page)
        indices.extend(struct.pack('<H', pages[page]))
    return bytes(indices + payload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = DIRECTORY / 'grapheme_pages.bin'
    data = pack()
    if args.check:
        if target.read_bytes() != data:
            parser.error('grapheme_pages.bin differs from the pinned property tables')
    else:
        target.write_bytes(data)
    print(f'{len(data)} bytes, {(len(data) - SCALARS // PAGE_SIZE * 2) // PAGE_SIZE} unique pages')
