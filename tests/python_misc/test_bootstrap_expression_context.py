"""Every expression form honors the expected storage or parameter type."""
import subprocess
import test_bootstrap_prelude as prelude
from dewy.reporting import SrcFile
from dewy.semantic import check

CASES = [
    'let values:array<uint8>=[2]\nlet code:int64=values[0]\nlet result=0x2400+code',
    'let f=(values:array<uint8 length=1>):>int64=>{let code:int64=values[0] return 0x2400+code}',
    'let value=[code=2 as uint8]\nlet code:int64=value.code\nlet result=0x2400+code',
    'let code:int64=0\nlet values:array<uint8>=[2]\ncode=values[0]\nlet result=0x2400+code',
]
ERRORS = [
    'let values:array<int64>=[2]\nlet bad:string=values[0]',
    'let value=[code=2]\nlet bad:string=value.code',
]


def test_native_expression_context(tmp_path):
    binary=prelude.module_driver(tmp_path)
    for index,text in enumerate(CASES):
        source=tmp_path/f'context-{index}.dewy'
        source.write_text(text)
        check.typecheck_and_resolve(SrcFile.from_path(source))
        result=subprocess.run([binary,source],capture_output=True,text=True,timeout=30,check=False)
        assert result.returncode==0,result.stdout+result.stderr
    for index,text in enumerate(ERRORS):
        source=tmp_path/f'context-error-{index}.dewy'
        source.write_text(text)
        result=subprocess.run([binary,source],capture_output=True,text=True,timeout=30,check=False)
        assert result.returncode!=0,text
