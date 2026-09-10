"""Dewy UTF-8 segmentation uses the hosted Unicode conformance corpus."""
import struct
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.unicode.data import (
    EXTENDED_PICTOGRAPHIC_RANGES,
    GRAPHEME_BREAK_RANGES,
    INDIC_CONJUNCT_BREAK_RANGES,
)
from dewy.semantic.unicode.generate import grapheme_runtime_tables
from dewy.semantic.unicode.graphemes import grapheme_boundary_byte_offsets
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_grapheme_runtime_tables_match_generated_data():
    for name, content in grapheme_runtime_tables(GRAPHEME_BREAK_RANGES, EXTENDED_PICTOGRAPHIC_RANGES, INDIC_CONJUNCT_BREAK_RANGES).items():
        assert (ROOT / 'library/unicode' / name).read_bytes() == content


def test_dewy_utf8_grapheme_boundaries(tmp_path):
    texts = ['', 'ASCII', 'e\u0301', '👩‍👩‍👧‍👦', '🇺🇸🇨🇦🇫', '\r\n', 'क्\u200dष']
    for line in (ROOT / 'tests/data/GraphemeBreakTest-16.0.0.txt').read_text().splitlines():
        tokens = line.split('#')[0].split()
        if tokens:
            texts.append(''.join(chr(int(token, 16)) for token in tokens if token not in {'÷', '×'}))
    cases = [text.encode('utf8') for text in texts]
    expected = [','.join(map(str, grapheme_boundary_byte_offsets(text))) for text in texts]
    invalid = [b'\x80', b'\xc0\xaf', b'\xc1\xbf', b'\xc2', b'\xe0\x80\x80', b'\xed\xa0\x80', b'\xf0\x80\x80\x80', b'\xf4\x90\x80\x80', b'\xf5\x80\x80\x80', b'\xe2\x82', b'\xc2A', b'\xff']
    cases.extend(invalid)
    expected.extend(['invalid'] * len(invalid))
    data = tmp_path / 'cases.bin'
    data.write_bytes(b''.join(struct.pack('<I', len(case)) + case for case in cases))
    source = tmp_path / 'graphemes.dewy'
    source.write_text(f'''
import p"{ROOT / 'library/unicode/graphemes.dewy'}" as segmentation
main=(argv:array<string>):>int64=>{{
    $runtime_assert argv.length =? 2
    let data=p(argv[1]).read_bytes
    if data isnt? array<uint8> return 1
    let offset:int64=0
    loop offset <? data.length {{
        let length=segmentation.word(data offset)
        offset+=4
        let bytes:array<uint8>=[]
        let index:int64=0
        loop index <? length {{
            $runtime_assert offset >=? 0 and offset <? data.length
            bytes.push(data[offset])
            offset+=1 index+=1
        }}
        let result=segmentation.boundaries(bytes)
        if result is? none {{printl('invalid') continue}}
        let parts:array<string>=[]
        loop boundary in result {{parts.push("{{boundary}}")}}
        printl(parts.join(','))
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve(), data], capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == expected
