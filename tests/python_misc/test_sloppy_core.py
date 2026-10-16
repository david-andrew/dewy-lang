"""Expected user behavior for the experimental source-level core."""
import os
import subprocess
from pathlib import Path

import pytest

CASES = {
    'answer': 'main=():>int64=>42',
    'calls': 'add=(a:int64 b:int64):>int64=>a+b\nmain=():>int64=>add(20 22)',
    'records': '''Vector:type=[x:int64 y:int64]
main=():>int64=>{let a=Vector[20 22] let b=a b.x=0 return a.x+a.y}''',
    'arrays': '''main=():>int64=>{let a:array<int64>=[20 22] let b=a b[0]=0 return a[0]+a[1]}''',
    'branches-loops': '''main=():>int64=>{let i:int64=0 loop i <? 3 {i+=1} return if i =? 3 42 else 1}''',
    'place': '''bump=(@x:int64):>void=>{x+=2}
main=():>int64=>{let x:int64=40 bump(@x) return x}''',
    'value-parameter': '''bump=(xs:array<int64>):>int64=>{xs[0]=0 return xs[0]}
main=():>int64=>{let xs:array<int64>=[42] bump(xs); return xs[0]}''',
    'floor': '''main=():>int64=>if (-7)//3 =? -3 and (-7)%3 =? 2 and 7//(-3) =? -3 and 7%(-3) =? -2 42 else 1''',
    'float': '''Vector:type=[x:float64 y:float64]
main=():>int64=>{let v=Vector[1.25 2.5] return if v.x*2.0 =? v.y 42 else 1}''',
    'unicode': 'main=():>int64=>{let α:int64=42 printl"é🙂 {α}" return α}',
    'argv': 'main=(args:array<string>):>int64=>if args.length =? 2 42 else 1',
    'array-iteration': 'main=():>int64=>{let sum:int64=0 loop x in [20 22] {sum+=x} return sum}',
    'range-ends': '''main=():>int64=>{let sum:int64=0 loop i in 0..3 {sum+=i}
loop i in [0..3) {sum+=i} loop i in [0..3] {sum+=i} return sum+27}''',
    'combined-continue': '''main=():>int64=>{let sum:int64=0
loop i in 0.. and i <? 8 {if i =? 3 continue if i =? 6 break sum+=i} return sum+30}''',
    'zipped-continue': '''main=():>int64=>{let sum:int64=0
loop x in [10 20 12] and i in 0.. {if i =? 1 continue sum+=x} return sum+20}''',
    'nested-combined': '''main=():>int64=>{let sum:int64=0
loop i in 0.. and i <? 3 {loop j in 0.. and j <? 2 {sum+=7}} return sum}''',
}
ERRORS = {
    'missing-place': ('bump=(@x:int64):>void=>{x+=2}\nmain=():>int64=>{let x:int64=40 bump(x) return x}', 'needs `@`'),
    'unbounded-int': ('main=():>int=>42', 'unbounded integer'),
    'grapheme-length': ('main=():>int64=>"é🙂".length', 'grapheme string length'),
    'grapheme-index': ('main=():>int64=>{let s="é🙂" printl(s[0]) return 42}', 'grapheme string indexing'),
    'proof-directive': ('$assert true\nmain=():>int64=>42', 'does not yet support'),
    'effect-contract': ('main=():>int64 & no_effects=>42', 'does not yet support'),
    'missing-name': ('# 🙂\nmain=():>int64=>missing', 'unknown'),
}


@pytest.fixture(scope='module')
def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER to the experimental source-level core')
    return Path(value).resolve(strict=True)


@pytest.mark.parametrize('name', CASES)
def test_core_values(compiler, tmp_path, name):
    source = tmp_path / f'{name}.dewy'
    source.write_text(CASES[name])
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    result = subprocess.run([binary, 'extra'], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 42, (result.returncode, result.stdout, result.stderr)
    if name == 'unicode':
        assert result.stdout == 'é🙂 42\n'


@pytest.mark.parametrize('name', ERRORS)
def test_core_rejects(compiler, tmp_path, name):
    body, diagnostic = ERRORS[name]
    source = tmp_path / f'{name}.dewy'
    source.write_text(body)
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode != 0 and diagnostic in built.stderr, built.stdout + built.stderr
    assert str(source) in built.stderr
    assert not binary.exists()


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_core_imports(compiler, tmp_path, extension):
    dependency = tmp_path / f'helper.{extension}'
    dependency.write_text('twice=(x:int64):>int64=>x*2' if extension == 'dewy'
                          else 'twice = (x: int) -> int: x * 2')
    source = tmp_path / 'main.dewy'
    source.write_text(f'from p"helper.{extension}" import twice\nmain=():>int64=>twice(21)')
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True,
                           text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    assert subprocess.run([binary], timeout=10, check=False).returncode == 42
