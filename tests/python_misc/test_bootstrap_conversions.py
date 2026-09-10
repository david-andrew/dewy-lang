"""Explicit conversion selects a method's target and keeps interpolation parts."""
import test_bootstrap_check as source_values

POINT = '''Point:type=[
    x:int64
    __as__=():>string=>"point:{x}"
    __as__ &= ():>int64=>x+100
]
'''
CASES = [
    '7 as int64',
    'let n:uint8=7\nn as int64',
    'let n:int64=7\nn as uint8',
    '"text" as string',
    '"value:{7}:{true}:{none}"',
    'let n:int64=7\n"value:{n}"',
    'let s:string="text"\n"[{s}]"',
    'let f=(x:int64):>int64=>x\n"{@f}"',
    'T:type=[x:int64]\nT as string',
    'T:type=[x:int64]\n"{T}"',
    POINT + 'Point[7] as int64',
    POINT + 'Point[7] as string',
    POINT + '"{Point[7]}"',
    POINT.replace('Point:type=', 'Point=type of ') + 'Point[7] as string',
    POINT.replace('Point:type=', 'Point=type of ') + 'Child=type of Point\nChild[7] as int64',
    'T:type=[__as__=():>string=>"static"]\nT[] as string',
    'T:type=[x:int64 __as__=():>string=>"safe" __as__ &= ():>int64=>{x+=1 return x}]\nT[7] as string',
    'T:type=[x:int64 __as__=():>string=>"safe" __as__ &= ():>int64=>{x+=1 return x}]\nlet t=T[7]\nt as int64',
]
ERRORS = [
    '7 as string',
    'true as string',
    '"text" as int64',
    '"{void}"',
    '"{1 2}"',
    'T:type=[x:int64 __as__=(n:int64):>string=>"x"]\nT[7] as string',
    'T:type=[x:int64 __as__=():>int64=>{x+=1 return x}]\nT[7] as int64',
    'T:type=[x:int64 __as__=():>int64=>{x+=1 return x}]\nconst t=T[7]\nt as int64',
]


def test_native_explicit_conversions_and_interpolation(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, unordered_instances=True)
