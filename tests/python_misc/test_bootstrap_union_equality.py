"""Equality with a literal alternative narrows a mixed union's tag."""
import test_bootstrap_check as source_values

CASES = [
    'Choice:type=0|[value:int64]\nlet read=(x:Choice):>int64=>{if x =? 0 return 0\nreturn x.value}',
    'Choice:type=0|[value:int64]\nlet read=(x:Choice):>int64=>{if x not=? 0 return x.value\nreturn 0}',
    'Choice:type=0|[value:int64]\nlet read=(x:Choice):>int64=>{if 0 =? x return 0\nreturn x.value}',
    "let read=(x:'a'|'b'):>bool=>{if x =? 'a' return true\nreturn false}",
    'BigInt:type=0|[sign:-1|1 limbs:array<uint64 length >? 0>]\nlet low=(x:BigInt):>uint64=>{if x =? 0 return 0\nreturn x.limbs[0]}',
    'Choice:type=0|[value:int64]\nconst ZERO=0\nlet read=(x:Choice):>int64=>{if x =? ZERO return 0\nreturn x.value}',
]


def test_native_literal_union_equality(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', [])
    source_values.test_native_source_values(tmp_path, function_types=True)
