"""Optional words materialize bigint payloads without re-evaluating their source."""

import test_bootstrap_check as source_values
from test_bootstrap_bigint_operators import PREFIX

CASES = [PREFIX + f'let convert=(value:{word}?):>BigInt?=>value'
         for word in ['int8', 'uint8', 'int64', 'uint64', 'addr']]
CASES += [PREFIX + body for body in [
    'let convert=(record:[length:addr?]):>BigInt?=>{let count:BigInt?=none count=record.length return count}',
    'let convert=(value:uint64?):>BigInt|string|none=>value',
    # A compatible word alternative requires no object materialization.
    'let convert=(value:int64?):>BigInt|int64|none=>value',
    'let convert=(value:int64):>BigInt|uint64|none=>value',
    'let convert=(value:int64?):>BigInt|uint64|none=>value',
    'let source=(@calls:int64 value:uint64?):>uint64?=>{calls+=1 return value}\nlet convert=(@calls:int64 value:uint64?):>BigInt?=>source(@calls value)',
]]
ERRORS = [PREFIX + body for body in [
    'let convert=(value:string?):>BigInt?=>value',
    'let convert=(value:int64?):>BigInt=>value',
]]


def test_native_optional_bigint_materialization(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
