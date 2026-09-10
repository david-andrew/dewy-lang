"""Literal enums retain their tag representation in fixed and grown arrays."""

import subprocess

import pytest
from test_array_field_call_borrows import _build


@pytest.mark.parametrize(
    "source",
    [
        "Sign:type=-1|1\nlet count:int64=0\nlet next=():>1=>{count+=1 return 1}\nlet main=():>int64=>{let value:Sign=next() return count+41}",
        "Sign:type=-1|1\nlet add=(left:Sign right:Sign):>int64=>left+right\nlet main=():>int64=>add(-1 1)+42",
        "Sign:type=-1|1\nBox:type=[sign:Sign]\nlet main=():>int64=>{let value=Box[-1] return value.sign+43}",
        'Op:type=addr|"and"|"or"|"xor"|"xnor"\nlet choose=(value:Op):>int64=>{if value is? addr return 0 else if value is? "xor"|"xnor" return 0 else return if value=?"and" 42 else 0}\nlet main=():>int64=>choose("and")',
        "Sign:type=-1|1\nlet main=():>int64=>{let values:array<Sign>=[-1 1] return (values[0] as int64)+(values[1] as int64)+42}",
        'Choice:type=0|"ready"|"done"\nlet main=():>int64=>{let values:array<Choice>=[] values.push("ready") values.push(0) let copy=values copy[0]="done" return if values[0] is? "ready" 42 else 0}',
        "Sign:type=-1|1\nlet make=():>array<Sign>=>[-1 1]\nlet main=():>int64=>{let values=make() if values.length<?2 return 0 return (values[0] as int64)+(values[1] as int64)+42}",
    ],
)
def test_enum_array_storage(tmp_path, source):
    binary = _build(tmp_path, source)
    result = subprocess.run([binary], capture_output=True, timeout=30, check=False)
    assert result.returncode == 42, result.stderr
