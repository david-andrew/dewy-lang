"""Concrete input types select generic branches without leaking block scopes."""
import subprocess

import test_bootstrap_prelude as prelude
from dewy.reporting import SrcFile
from dewy.semantic import check

CASES = [
    'let text=<T>(value:T):>string=>{if value is? string return value else return value as string}\nlet result=text("hello")',
    'Record:type=[value:int64]\nlet extract=<T>(x:T):>int64=>{if x is? Record return x.value else return 0}\nlet a=extract([value=42])\nlet b=extract(99)',
    'let f=<T>(x:T):>int64=>{if not (x is? string) return 42 else return x.length}\nlet answer=f(1)',
    'let f=(x:any):>int64=>{if x is? int64 return x else return 0}',
    'Record:type=[value:int64]\nlet f=(x:Record|string):>int64=>{if x is? Record return x.value else return 0}',
]
ERRORS = [
    'let x:int64=1\nif x is? int64 {let hidden:int64=2}\nlet leaked=hidden',
    'if false {let value=undefined_name}',
]


def test_native_decided_type_branches(tmp_path):
    binary = prelude.module_driver(tmp_path)
    for index, text in enumerate(CASES):
        source = tmp_path / f'decided-{index}.dewy'
        source.write_text(text)
        check.typecheck_and_resolve(SrcFile.from_path(source))
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    for index, text in enumerate(ERRORS):
        source = tmp_path / f'decided-error-{index}.dewy'
        source.write_text(text)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode != 0, text
