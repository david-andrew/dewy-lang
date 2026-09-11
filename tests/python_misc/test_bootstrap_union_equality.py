"""Equality with a literal alternative narrows a mixed union's tag."""
import subprocess

import test_bootstrap_check as source_values

CASES = [
    'let x:int64|none=1\nx=none\nx =? 1',
    'let x:int64|none=1\nx=none\nx not=? 1',
    'let x:int64|string=1\nx="a"\nx =? 1',
    'let same=(a:string|none b:string):>bool=>a =? b',
    'let same=(a:string b:string|none):>bool=>a not=? b',
    'let same=(a:int64|none b:int64):>bool=>a =? b',
    'let read=(a:int64|none):>int64=>{if a =? 3 {return a} return 0}',
    'let read=(a:int64|none):>int64=>{if a not=? 3 {return 0} return a}',
    'let same=(a:int64|none b:none|int64):>bool=>a =? b',
    'let same=(a:int64|string|none b:none|string|int64):>bool=>a not=? b',
    'let same=(a:[parent:string|none] b:string):>bool=>a.parent =? b',
    'let make=():>string|none=>none\nlet same=(b:string):>bool=>make() =? b',

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

    # The hosted implementation also leaves differing alternatives pending.
    # The shared driver deliberately fails (rather than calling this a proved
    # rejection) when a checker reports an implementation placeholder.
    pending = tmp_path / 'different-unions.dewy'
    pending.write_text('let same=(a:int64|none b:string|none):>bool=>a =? b')
    executable = source_values._native_driver(tmp_path)
    result = subprocess.run([executable, 'invalid', 'true', 'false', 'false', pending],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 1
    assert 'equality between unions with different alternatives' in result.stderr
