"""Record literals keep the selected union member's field checking context."""
import subprocess

import test_bootstrap_prelude as prelude

from dewy.reporting import SrcFile
from dewy.semantic import check

CASES = [
    # A union test after a failed family test must select its surviving
    # descendants, including at branch joins and common-field reads.
    'Token:type=$abstract type of [loc:int64]\nA:type=type of Token & [a:bool]\nB:type=type of Token & [b:string]\nC:type=type of Token & [c:int64]\nlet read=(token:Token):>int64=>{if token is? A return token.loc\nif token is? A|B|C {if token isnt? A|B {token.c;} return token.loc} return token.loc}',

    'Base:type=$abstract type of []\nB:type=type of Base & [value:bool]\nI:type=type of Base & [value:[x:int64]]\nlet read=(node:Base):>int64=>{if node is? B return if node.value 1 else 0\nif node is? I return node.value.x\nreturn 0}',
    'Base:type=$abstract type of []\nB:type=type of Base & [value:bool|none]\nI:type=type of Base & [value:int64|none]\nlet read=(node:Base):>int64=>{if node is? B {if node.value is? bool return if node.value 1 else 0}\nif node is? I {if node.value is? int64 return node.value}\nreturn 0}',
    'Base:type=$abstract type of []\nB:type=type of Base & [value:bool]\nI:type=type of Base & [value:int64]\nlet change=(node:Base):>void=>{if node is? B {node.value=true}\nelse if node is? I {node.value=42}}',
    'Token:type=$abstract type of [value:int64]\nWord:type=type of Token\nNumber:type=type of Token & [base:int64]\nlet name=(token:Token):>string=>{let value=token.value if token is? Number {value=token.base} return token.typename}',
    'Token:type=$abstract type of [value:int64]\nWord:type=type of Token\nNumber:type=type of Token & [base:int64]\nlet value=(token:Token):>int64=>{if token is? Number {token.base;} return token.value}',

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
    'Base:type=$abstract type of []\nB:type=type of Base & [value:bool]\nI:type=type of Base & [value:int64]\nlet change=(node:Base):>void=>{if node is? B {node.value=true}\nelse if node is? I {node.value=false}}',
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
