"""Record literals keep the selected union member's field checking context."""
import subprocess

from dewy.reporting import SrcFile
from dewy.semantic import check
import test_bootstrap_prelude as prelude

CASES = [
    # Scalar field predicates are checked at construction; alias composition
    # retains them and does not evaluate an unused default.
    'Base:type=type of [code:1|2=1]\nChild:type=type of Base & [code=3]',

    'Report:type=type of [severity:"error"|"warning"="warning"]\nError:type=type of Report & [severity="error"]\nlet report=Error[]',
    'Base:type=type of [code:1|2=1]\nChild:type=type of Base & [code=2]\nlet child=Child[]',

    'Choice:type=0|[x:int64]\nlet f=(x:int64):>Choice=>[x=x]',
    'Choice:type=0|[x:int64<x >? 0>]\nlet f=(x:int64<x >? 0>):>Choice=>[x=x]',
    'Choice:type=0|[x:int64]|[y:bool]\nlet f=(y:bool):>Choice=>[y=y]',
    'BigInt:type=0|[sign:-1|1 limbs:array<uint64 length >? 0>]\nR:type=0|[numerator:BigInt & ~0 denominator:BigInt<sign =? 1>]\nlet f=(numerator:BigInt denominator:BigInt<sign =? 1>):>R=>{if numerator =? 0 return 0\nreturn [numerator=numerator denominator=denominator]}',
    'A:type=type of [text:string]\nB:type=type of [code:int64 text:string]\nlet f=(ending:A|B):>string=>ending.text',
    'A:type=type of [text:string]\nB:type=type of [text:int64]\nlet f=(ending:A|B|none):>string|int64|none=>ending.text',
]
ERRORS = [
    'Report:type=type of [severity:"error"|"warning"="warning"]\nError:type=type of Report & [severity="unknown"]',

    "Choice:type=0|[x:int64]\nlet f=():>Choice=>[x='wrong']",
    'Choice:type=0|[x:int64]|[x:bool]\nlet f=():>Choice=>[x=1]',
    'A:type=type of [text:string]\nB:type=type of [other:string]\nlet f=(ending:A|B):>string=>ending.text',
]


def test_native_union_record_context(tmp_path):
    binary = prelude.module_driver(tmp_path)
    for index, text in enumerate(CASES):
        source = tmp_path / f'record-{index}.dewy'
        source.write_text(text)
        check.typecheck_and_resolve(SrcFile.from_path(source))
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    for index, text in enumerate(ERRORS):
        source = tmp_path / f'error-{index}.dewy'
        source.write_text(text)
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode != 0, text
