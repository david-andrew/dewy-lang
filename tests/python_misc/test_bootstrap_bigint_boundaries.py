"""Prelude numeric aliases and word/constant promotions at native boundaries."""
import test_bootstrap_check as source_values

BIG = 'BigInt:type=0|[sign:-1|1 limbs:array<uint64 length >? 0>]\n'
HELPERS = BIG + '''
let _bigint_from_int=(value:int64):>BigInt=>0
let _bigint_from_uint=(value:uint64):>BigInt=>0
'''
CASES = [
    BIG + 'let take=(value:bigint):>bigint=>value\ntake(7)',
    BIG + 'let take=(value:bigint & ~0):>bigint=>value\ntake(7)',
    BIG + 'let take=(value:bigint):>bigint=>value\ntake(1267650600228229401496703205393)',
    HELPERS + 'let take=(value:bigint):>bigint=>value\nlet word:int64=7\ntake(word)',

    BIG + 'let value:bigint=0\nvalue',
    BIG + 'let value:bigint=1\nvalue',
    BIG + 'let value:bigint = -1\nvalue',
    BIG + 'let value:bigint=1267650600228229401496703205393\nvalue',
    BIG + 'let value=1267650600228229401496703205393\nvalue',
    BIG + 'let value:bigint & ~0=7\nvalue',
    BIG + 'let make=():>bigint=>7\nmake()',
    HELPERS + 'let word:int64=7\nlet value:bigint=word\nvalue',
    HELPERS + 'let word:uint64=18446744073709551615\nlet value:bigint=word\nvalue',
]
ERRORS = [BIG + 'let value:bigint & ~0=0', BIG + 'let take=(value:bigint & ~0):>bigint=>value\ntake(0)']


def test_native_bigint_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path)
