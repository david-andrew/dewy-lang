"""A callable expectation supplies unannotated lambda inputs before its body."""
import subprocess

import test_bootstrap_prelude as prelude
from dewy.reporting import SrcFile
from dewy.semantic import check

CASES = [
    'Span:type=[start:int64 stop:int64]\nlet sort=(xs:array<Span>):>void=>xs.sort(key=s=>s.start)',
    'Span:type=[start:int64]\nlet sort=(xs:array<Span>):>void=>xs.sort(reverse=true key=s=>s.start)',
    'Fn:type=(x:[value:int64]):>int64\nlet f:Fn=x=>x.value\nlet answer=f([value=42])',
    'Fn:type=(x:[value:int64]):>int64\nlet apply=(f:Fn):>int64=>f([value=42])\nlet answer=apply(x=>x.value)',
    'Fn:type=(x:int64):>int64\nlet f:Fn=x=>x+1\nlet answer=f(41)',
]
ERRORS = [
    'Span:type=[start:int64]\nlet sort=(xs:array<Span>):>void=>xs.sort(key=(s:any)=>s.start)',
    'Span:type=[start:int64]\nlet sort=(xs:array<Span>):>void=>xs.sort(key=s=>s.missing)',
]


def test_native_contextual_lambda_parameters(tmp_path):
    binary = prelude.module_driver(tmp_path)
    for index, text in enumerate(CASES):
        source = tmp_path / f'lambda-{index}.dewy'
        source.write_text(text)
        check.typecheck_and_resolve(SrcFile.from_path(source))
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    for index, text in enumerate(ERRORS):
        source = tmp_path / f'lambda-error-{index}.dewy'
        source.write_text(text)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode != 0, text
