"""The archived layout: `name = (x:int64):>int64 => body`."""
import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def compiler():
    path = os.environ.get('DEWY_CORE_COMPILER')
    if not path:
        pytest.skip('set DEWY_CORE_COMPILER for formatter checks')
    return Path(path).resolve(strict=True)


CASES = [
    ('main=()=>{}', 'main = () => {}'),
    ('f=(x:int64):>int64=>x+1', 'f = (x:int64):>int64 => x+1'),
    ('f = (x: int64) :> int64 => x', 'f = (x:int64):>int64 => x'),
    ('Point:type=[x:int64 y:int64=22]', 'Point:type = [x:int64 y:int64=22]'),
    ('f=(a b=a)=>a', 'f = (a b=a) => a'),
    ('main=()=>{\nx+=1\nlet [a b]=p\nxs[0]=2\nprintl(f(scale=3 7))\n}',
     'main = () => {\n    x += 1\n    let [a b] = p\n    xs[0] = 2\n    printl(f(scale=3 7))\n}'),
    ('T=type of [id:int64\nwidth=()=>stop-start\ng=<T>(x:T):>T=>x\nn=3]',
     'T = type of [id:int64\n    width = () => stop-start\n    g = <T>(x:T):>T => x\n    n=3]'),
    ('x=array<int64 length=3>', 'x = array<int64 length=3>'),
    ('m=(a)=>a\n& b\nc=(x)=>\nx', 'm = (a) => a\n    & b\nc = (x) =>\n    x'),
    ('xs.sort(key=m=>m.length reverse=true)', 'xs.sort(key=m => m.length reverse=true)'),
    ('let size=match v {n:int64=>n <none>=>0}', 'let size = match v { n:int64 => n <none> => 0 }'),
]


@pytest.mark.parametrize('text,expected', CASES)
def test_core_format_style(compiler, text, expected):
    result = subprocess.run([compiler, 'fmt', '-'], input=text + '\n', capture_output=True,
                            text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected + '\n'
