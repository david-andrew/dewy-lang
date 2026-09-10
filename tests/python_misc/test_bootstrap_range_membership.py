"""Exact membership and runtime range descriptors use the same endpoints."""
import test_bootstrap_check as source_values

CASES = [
    '7 in? [1..10]',
    '7 not in? [1..10]',
    '7 in? [1..7)',
    '1 in? (1..7]',
    '7 in? [9..1]',
    '7 in? [9,7..1]',
    '6 in? [9,7..1]',
    '7 in? (9,7..1)',
    '7 in? [1,3..]',
    '7 in? [..7]',
    '7 in? [7..]',
    '18446744073709551616 in? [0,2..18446744073709551618]',
    'let r=1..10\n7 in? r',
    'let includes=(n:int64):>bool=>n in? [1..10]\nincludes(7)',
    'let includes=(n:int64 lo:int64 hi:int64):>bool=>n in? (lo..hi]\nincludes(7 1 10)',
    'let includes=(n:int64):>bool=>n in? [9,7..1]\nincludes(7)',
    'let includes=(n:int64):>bool=>n not in? [1,3..]\nincludes(7)',
]
ERRORS = [
    '3 in? [1,1..5]',
    'let includes=(n:string):>bool=>n in? [1..5]',
]


def test_native_range_membership(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
