"""Membership and set construction instantiate their ordinary source helpers."""
import test_bootstrap_check as source_values

ARRAYS = (source_values.ROOT / 'library/arrays.dewy').read_text()
STRINGS = (source_values.ROOT / 'library/strings.dewy').read_text()
CASES = [
    ARRAYS + '\n2 in? [1 2 3]',
    ARRAYS + '\nlet values:array<addr>=[1 2]\nlet needle:int64=2\nneedle not in? values',
    ARRAYS + '\nlet values:array<string>=["one" "two"]\n"one" in? values',
    STRINGS + '\nlet letters=set"abba"\nletters.length',
    STRINGS + '\nlet values:array<int64>=[1 2 1]\nlet members=set(values)\nmembers.length',
    'let set=(x:int64):>int64=>x\nset(7)',
]
ERRORS = [
    '2 in? [1 2 3]',
    'set"abc"',
    'set(7)',
    ARRAYS + '\nlet values:array<string>=["one"]\n2 in? values',
]


def test_native_library_membership_and_set_construction(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
