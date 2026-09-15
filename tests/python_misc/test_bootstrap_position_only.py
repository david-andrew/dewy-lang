"""Position-only slots retain lexical names without accepting keyword calls."""
import test_bootstrap_check as source_values
import test_bootstrap_lowering as native_lowering
import subprocess

from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

CASES = [
    'let add=(<left:int64> right:int64):>int64=>left+right\nadd(20 right=22)',
    'let increment=(<value:int64=1>):>int64=>value+1\nincrement()',
    'let seed:int64=40\nlet f=(<value:int64=seed>):>int64=>value+2\nf()',
    'let f=(<value:int64=1>):>int64=>value\nf(42)',
    'let choose=<T>(<value:T>):>T=>value\nchoose(42)',
    'let same=(<value:int64>):>int64=>value\nlet f=@same\nf(42)',
    'let set=(<@value:int64>):>void=>{value=42}\nlet x:int64=0\nset(@x)\nx',
]
ERRORS = [
    'let f=(<value:int64>):>int64=>value\nf(value=42)',
    'let f=(<value:int64=1>):>int64=>value\nf(value=42)',
    'let choose=<T>(<value:T>):>T=>value\nchoose(value=42)',
    'let f=(<x:int64> x:int64):>int64=>x',
    'let f=(<x:int64 y:int64>):>int64=>x',
    'let f=(<>):>int64=>42',
    'let f=(<@x:int64=1>):>int64=>x',
]


def test_native_position_only_checking(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)


def test_native_position_only_execution(tmp_path):
    cases = [
        ('let add=(<left:int64> right:int64):>int64=>left+right\nlet main=():>int64=>add(20 right=22)', 42),
        ('let seed:int64=0\nlet next=():>int64=>{seed+=1 return seed}\nlet f=(<value:int64=next()>):>int64=>value\nlet main=():>int64=>{f(99); f(); f(); return seed+40}', 42),
        ('let same=(<value:int64>):>int64=>value\nlet main=():>int64=>{let f=@same return f(42)}', 42),
        ('let set=(<@value:int64>):>void=>{value=42}\nlet main=():>int64=>{let x:int64=0 set(@x) return x}', 42),
    ]
    binary = native_lowering.build_native_lowering_driver(tmp_path)
    for index, (text, expected) in enumerate(cases):
        source = tmp_path / f'case-{index}.dewy'
        source.write_text(text)
        compiled = subprocess.run([binary, source], capture_output=True, text=True, timeout=60)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        output = source.with_suffix('.udewy')
        output.write_text(compiled.stdout)
        for target in ('x86_64', 'c'):
            assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
            result = subprocess.run([cache_artifact(output).resolve()], timeout=10)
            assert result.returncode == expected, text
