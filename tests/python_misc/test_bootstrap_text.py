"""Text storage shapes and the ordinary library-backed member path."""
import test_bootstrap_check as source_values

CASES = [
    'let text="abc"\ntext',
    'let text="abc"\ntext.length',
    'let text="abc"\ntext="abc"\ntext',
    'let text:string="abc"\ntext="def"\ntext',
    '"café" as array<uint8>',
    '"café" as array<uint32>',
    '"café" as array<grapheme>',
    '"👨‍👩‍👧‍👦" as array<char>',
    'let text:string="café"\ntext as array<uint8>',
    'let bytes:array<uint8>="café"\nbytes.length',
    'let scalars:array<uint32>="café"\nscalars.length',
    'let clusters:array<grapheme>="café"\nclusters.length',
    'let bytes:array<uint8>=[97]\nbytes as string|none',
    'let clusters:array<grapheme>=["e" "x"]\nclusters as string',
    'let x:int64=255\nx transmute uint8',
    'uint8.max',
    'int64.min',
    'uint64.max',
    'let uint8=[max=7]\nuint8.max',
    'let _string_startswith=(text:string prefix:string):>bool=>text.length >=? prefix.length\n"abc".startswith("a")',
    'let _string_trim=(text:string):>string=>text\n"abc".trim',
    'let _string_replace=(text:string old:string new:string):>string=>new\n"abc".replace(old="a" new="b")',
    (source_values.ROOT / 'library/strings.dewy').read_text(),
    (source_values.ROOT / 'library/arrays.dewy').read_text(),
]
ERRORS = [
    'let text="abc"\ntext="def"',
    'let bytes:array<uint8>=[97]\nbytes as string',
    'let scalars:array<uint32>=[97]\nscalars as string',
    '"abc" transmute array<uint8>',
    'let bytes:array<uint8>=[97]\nbytes transmute string',
    'let bytes:array<uint8 length=2>="abc"',
    'uint8.missing',
    '"abc".trim',
    'let _string_find=(text:string needle:string):>int64=>0\n"abc".find',
]


def test_native_text_materialization_and_library(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
