"""Exact real constants stay fractions until a use selects a representation."""
import test_bootstrap_check as source_values

CASES = [
    '1.25',
    '0.0',
    '0.000000000000000000001',
    '123_456.7_890',
    '1e30',
    '1.25e-30',
    '-1.25',
    '1.25+2.5',
    '1.25-2.5',
    '1.25*2.5',
    '1.25/2.5',
    '1/3',
    '0/3',
    '1.25 =? 5/4',
    '1.25 not=? 2',
    '1.25 <? 2',
    '-1.25 >=? -2',
    'const value=1.25\nvalue+0.75',
    'const a=1/3\nconst b=2/3\na+b',
    'let __add__=(a:int64 b:int64):>int64=>7\n1+2',
]
ERRORS = [
    '1.25/0',
    '1/0.0',
    '1.25+"text"',
    '0x1.2',
    '1p2',
]


def test_native_exact_numeric_constants(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
