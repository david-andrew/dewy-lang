"""User constructor signatures compete with the ordinary field-wise form."""
import test_bootstrap_check as source_values

CASES = [
    'T:type=[x:int64]\nT &= (s:string):>T=>T[s.length]\nT[2]',
    'T:type=[x:int64]\nT &= (s:string):>T=>T[s.length]\nT("abc").x',
    'T:type=[x:int64]\nT &= (s:string):>T=>T[s.length]\nT(s="abc").x',
    'T:type=[x:int64]\nT &= (s:string):>T=>T[s.length]\nT[x=3].x',
    'T:type=[x:int64]\nT &= (s:string)=>T[s.length]\nT("abc").x',
    'T:type=[x:int64]\nT &= (flag:bool):>T=>T[if flag 1 else 0]\nT(true).x',
    'T:type=[x:int64]\nT &= (s:string):>T=>T[s.length]\nT &= (flag:bool):>T=>T[if flag 1 else 0]\nT(false).x',
    'T:type=const[x:int64 y:int64=x]\nT &= (s:string):>T=>T[s.length]\nT("abc").y',
    'T:type=[x:int64 get=()=>x]\nT &= (s:string):>T=>T[s.length]\nT("abc").get',
]
ERRORS = [
    'T:type=[x:int64]\nT &= 5',
    'T:type=[x:int64]\nT &= (s:string):>T=>T[s.length]\nT(true)',
    'T:type=[x:int64]\nT &= (s:string):>T=>T[s.length]\nT(s=1)',
    'T:type=[x:int64]\nT &= (s:string):>T=>T[s.length]\nT(missing="abc")',
    'T=$abstract type of [x:int64]\nT &= (s:string):>T=>T[s.length]',
]


def test_native_constructor_overloads(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, unordered_instances=True)
