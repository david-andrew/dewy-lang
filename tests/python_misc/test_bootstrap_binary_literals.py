"""Based-string packing retains byte lengths and the hosted reserved radixes."""
import test_bootstrap_check as source_values

CASES = [
    '0x"61 62 63"',
    '0b"1"',
    '0q"123"',
    '0o"1234"',
    '0u"01AV"',
    '0g"aZ-_=="',
    '0x"ab_cd"',
    '0x""',
    '0x"616263".length',
    '0x"616263"[1]',
    'let bytes:array<uint8>=0x"616263"\nbytes.length',
    'let bytes:array<uint8 length=3>=0x"616263"\nbytes[1]',
    '0x"616263" as array<uint8>',
    '0x"616263" as string|none',
    'let read=(bytes:array<uint8>):>uint8=>bytes[0]\nread(0x"61")',
]
ERRORS = [
    '0d"123"',
    '0t"12T"',
    '0g"ab=c"',
    'let bytes:array<uint8 length=2>=0x"616263"',
    '0x"61" as string',
    '0x"61" transmute uint8',
    '0x"61"[1]',
]


def test_native_binary_literal_materialization(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
