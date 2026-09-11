"""Compound operands do not inherit the destination's store refinements."""
import test_bootstrap_check as source_values

CASES = [
    'let x:int64<n=>n>=?5>=5\nx+=1\nx',
    'let box:[x:int64<n=>n>=?5>]=[x=5]\nbox.x+=1\nbox.x',
    "let d:dict<string int64<n=>n>=?5>>=['x'->5]\nd['x']+=1\nd['x']",
    'let f=(names:array<int64>):>int64=>{let at:addr<i=>i<=?names.length>=0 loop at <? names.length {at+=1} return at}',
]


def test_native_compound_store_refinements(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', [])
    source_values.test_native_source_values(tmp_path, function_types=True)
