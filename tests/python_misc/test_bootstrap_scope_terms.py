"""Local refinement terms resolve to lexical value bindings."""
import test_bootstrap_check as source_values

CASES = [
    'let names:array<int64>=[]\nlet at:addr<i => i <=? names.length>=0\nat',
    'let limit:int64=42\nlet value:int64<v => v <=? limit>=0\nvalue',
    'let names:array<int64>=[42]\nlet at:addr<i => i <? names.length>|none=0\nat',
    'let f=(names:array<int64>):>void=>{let at:addr<i => i <=? names.length>=0}',
]
ERRORS = [
    'let at:addr<i => i <=? missing.length>=0',
    'let f=():>int64=>1\nlet at:int64<i => i <=? f>=0',
]


def test_native_local_refinement_terms(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
