"""Method implementations supply real protocol slots and prove contracts."""
import test_bootstrap_check as source_values

CASES = [
    'F:type=(x:int64):>int64\nP=$abstract type of [f:F]\nT=type of P & [f=(x:int64):>int64=>x+1]\nT[].f(2)',
    'F:type=(x:int64):>int64\nP=$abstract type of [f:F]\nT=type of P & [f=(x:int64):>int64=>x+1]\nT.f(2)',
    'F:type=(x:int64):>int64\nP=$abstract type of [f:F]\nT=type of P & [f=(x:int64):>int64=>x+1]\nT[f=(x:int64):>int64=>x+2].f(2)',
    'F:type=():>int64\nP=$abstract type of [f:F]\nT=type of P & [f=():>int64=>7]\nT[].f',
    'F:type=(x:int64):>int64<i=>i >? 0>\nP=$abstract type of [f:F]\nT=type of P & [f=(x:int64):>int64=>1]\nT.f(2)',
    'F:type=(x:int64):>int64<i=>i >? 0>\nP=$abstract type of [f:F]\nT=type of P & [f=(x:int64)=>1]\nT.f(2)',
    'F:type=(src:string):>int64<i=>i <=? src.length>\nP=$abstract type of [f:F]\nT=type of P & [f=(src:string):>int64=>src.length]\nT.f("abc")',
]
ERRORS = [
    'F:type=(x:int64):>int64\nP=$abstract type of [f:F]\nT=type of P & [f=(x:string):>int64=>x.length]',
    'F:type=(x:int64):>int64\nP=$abstract type of [f:F]\nT=type of P & [f=(x:int64):>bool=>true]',
]


def test_native_protocol_method_slots(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path)
