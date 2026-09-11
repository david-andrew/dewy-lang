"""Named slots are removed before binding subsequent positional arguments."""

import test_bootstrap_check as source_values

COMBINE = 'let combine=(left:int64 scale:int64=2 right:int64):>int64=>left+right*scale\n'
CASES = [COMBINE + f'combine({args})' for args in [
    'scale=2 10 16', 'right=16 10 2', '10 scale=2 16',
    'right=16 left=10', 'left=10 2 right=16', 'right=16 10',
]]
CASES += [
    'T:type=[x:int64 add=(left:int64 right:int64):>int64=>x+left+right]\nT[20].add(right=2 20)',
    'T:type=[x:int64 add=(left:int64 right:int64):>void=>{x+=left+right}]\nlet t=T[20]\nt.add(right=2 20)\nt.x',
    'let mix=(word:uint8 flag:bool):>uint8=>word\nmix(flag=true 42)',
    'let choose=<T>(first:T second:T):>T=>first\nchoose(second=true false)',
    'let change=(value:int64 @target:int64):>void=>{target=value}\nlet x:int64=0\nchange(value=42 @x)\nx',
    'let ints=(first:int64 second:int64):>int64=>first\nlet flags=(first:bool second:bool):>bool=>first\nlet pick=@ints & @flags\npick(second=true false)',
    'let ints=(first:int64 second:int64):>int64=>first\nlet flags=(flag:bool other:bool):>bool=>flag\nlet pick=@ints & @flags\npick(other=true false)',
]
ERRORS = [COMBINE + f'combine({args})' for args in [
    '10 left=20 16', 'scale=2 10', 'scale=2 10 16 20',
    'scale=2 scale=3 10 16', 'unknown=2 10 16',
]]
ERRORS += [
    'let f=(x:int64 y:bool):>int64=>x\nf(y=true false)',
]


def test_native_ordered_call_arguments(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
