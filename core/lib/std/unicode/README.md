# Unicode grapheme data

These are the Unicode 16.0.0 grapheme-break, Indic-conjunct-break and extended-
pictographic tables already generated for Dewy under `library/unicode/`. Each
sorted nine-byte record contains little-endian 32-bit start/end code points and
one property byte. The scanner is in `../graphemes.jo`.

The source URLs and hashes are pinned in
`dewy/semantic/unicode/generate.py`; that generator produces the existing
`library/unicode/*.bin` files. After an intentional Unicode update, copy these
three tables here and run the core conformance test against the updated official
`tests/data/GraphemeBreakTest-16.0.0.txt` corpus. Normal builds embed the local
files and need no network or old compiler.

Unicode data copyright © Unicode, Inc. The accompanying `LICENSE.txt` is the
Unicode License V3, retrieved from <https://www.unicode.org/license.txt> on
2026-10-16. The conformance fixture retains its own Unicode copyright header.
