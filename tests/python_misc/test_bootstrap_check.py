"""Native source expressions enter HIR through the shared lexical/type arenas."""

import json
import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, ty
from dewy.semantic.hir_display import type_to_dewy
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    '1', "'hello'", 'true', 'none', '1 + 2', '3 >? 2',
    'let x:int64 = 1\nx + 2',
    'let x:int64=1\nx+=2\nx',
    'let p=[x=1]\np.x+=2\np.x', 'const x = 1\nx', '[1 2]',
    'let x:int64 = 1\nx = 2\nx', 'let xs:array<int64> = []\nxs',
    'Count:type = int64\nlet n:Count = 7\nn',
    'let f=(x:int64):>int64 => x + 1\nf(7)',
    'let f=(x:int64):>int64 => { return x }\nf(8)',
    'let first=():>int64 => later()\nlet later=():>int64 => 9\nfirst()',
    'let f=(x:int64|string):>int64 => if x is? int64 x else 0\nf(7)',
    'let f=(x:bool):>int64 => { if x return 1 return 2 }\nf(false)',
    'if true 1 else 2',
    'let xs:array<int64>=[1]\nxs.push(2)\nxs.length',
    'let xs=[1]\nxs.push(2)\nxs.length',
    'let xs:array<int64>=[1]\nxs.pop',
    'let xs:array<int64>=[1]\nxs.clear\nxs.length',
    'let xs:array<int64>=[1]\nxs.insert(2 0)\nxs.truncate(1)\nxs.length',
    'let xs:array<int64>=[1]\nxs.reserve(4)\nxs.length',
    'let xs:array<string>=["a" "b"]\nxs.join(",")',
    'let f=():>int64 => 7\nf',
    'let f=():>int64 => 7\nlet alias=@f\nalias()',
    'let set=(@x:int64):>void => {x=7}\nlet x:int64=1\nset(@x)\nx',
    'let set=(@x:int64):>void => {x=7}\nlet p=[x=1]\nset(@p.x)\np.x',
    'let set=(@x:int64 @y:int64):>void => {x=7 y=9}\nlet p=[x=1 y=2]\nset(@p.x @p.y)\np',
    'let f=(@x:int64|string):>bool => {x="changed" return true}\nlet g=(@x:int64|string):>bool => x is? int64 and f(@x)\nlet x:int64|string=1\ng(@x)',
    'let f=(x:int64|string):>bool => x is? int64 and x >? 0\nf(7)',
    'let f=(x:int64|string):>bool => x isnt? int64 or x >? 0\nf(7)',
    'let f=(x:bool y:bool):>bool => x nand y\nf(true false)',
    'let f=(x:bool y:bool):>bool => x nor y\nf(true false)',
    'let x:int64|string=1\n{ x="done" }\nx',
    'let xs=[1 2]\nxs.length',
    '"hello".length',
    '[x=1 y=2]',
    'let p=[x=1]\np.x=3\np.x',
    'let f=(x:int64=3):>int64 => x\nf()',
    'let x:int64=9\nlet f=(x:int64 y:int64=x+1):>int64 => y\nf(3)',
    'let p:[x:int64 y:string]=[x=2 y="hi"]\np',
    'let p=[x=1 y=2]\np.x',
    'Point:type=[x:int64 y:int64]\nPoint[1 2]',
    'Point:type=[x:int64 y:int64=3]\nlet p=Point[x=2]\np.y',
    'Point:type=const [x:int64=2 y:int64=x+1]\nPoint[]',
    'let seed:int64=4\nPoint:type=[x:int64=seed]\nlet f=(seed:string):>Point => Point[]\nf("shadow")',


]


ERROR_CASES = [
    'let xs:array<int64 length=1>=[1]\nxs.push(2)',
    'let xs:array<int64>=[]\nxs.pop',
    'let xs:array<int64>=[1]\nxs.insert(2 3)',
    'let xs:array<int64>=[1]\nxs.truncate(-1)',
    'const p=[x=1]\np.x=2',
    'let change=(@x:int64|string):>bool => {x="changed" return true}\nlet bad=(@x:int64|string):>int64 => {if x is? int64 and change(@x) return x+1 return 0}',

    'let f=(@x:int64):>void => {}\nlet x:int64=1\nf(x)',
    'let f=(x:int64):>void => {}\nlet x:int64=1\nf(@x)',
    'let f=(@x:int64):>void => {}\nconst x:int64=1\nf(@x)',
    'let f=(@x:int64 @y:int64):>void => {}\nlet x:int64=1\nf(@x @x)',
    'let f=(@p:[x:int64] @x:int64):>void => {}\nlet p=[x=1]\nf(@p @p.x)',
    'let x:int64=1\nlet escaped=@x',
    'let f=(@x:int64=1):>void => {}',
    'let x:int64=1\nx="wrong"',
    'const x=1\n{x=2}',
    'let f=():>int64 => "wrong"\nf()',
    'let f=(x:int64):>int64 => x\nf(x=1 x=2)',
    '[x=1 x=2]',
    'Point:type=[x:int64]\nPoint[y=1]',
    'Point:type=[x:int64]\nPoint[]',
    'Point:type=[x:int64]\nPoint[1 2]',
    'Point:type=[x:int64 y:int64]\nPoint[1 x=2]',
    'Point:type=const [x:int64]\nlet p=Point[1]\np.x=2',
]


def test_native_source_values(tmp_path):
    expected = []
    for text in CASES:
        ty.reset_program_brands()
        module, _ = check._typecheck_module(SrcFile(None, text))
        expected.append(type_to_dewy(module.type))
    for text in ERROR_CASES:
        ty.reset_program_brands()
        with pytest.raises((check.UserError, check.TypeCheckError, check.NotImplementedYet)):
            check._typecheck_module(SrcFile(None, text))
    cases = ' '.join(json.dumps(text).replace('{', r'\{') for text in CASES)
    errors = ' '.join(json.dumps(text).replace('{', r'\{') for text in ERROR_CASES)
    source = tmp_path / 'check.dewy'
    source.write_text(f'''from reporting import SrcFile, Error
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/check.dewy'}" as checking
import p"{ROOT / 'dewy/bootstrap/semantic/type_display.dewy'}" as display
main = ():>int64 => {{
    let cases:array<string> = [{cases}]
    let failures:int64 = 0
    loop text in cases {{
        let source = SrcFile['fixture' text]
        let parsed = parser.parse(source)
        if parsed is? Error {{ parsed.fail return 1 }}
        let session = contexts.Session[]
        let lexical = contexts.begin(source parsed.nodes @session)
        let environment = checking.begin(lexical @session)
        let module = checking.block(parsed.root environment @session)
        if module is? Error {{ module.fail failures += 1 continue }}
        let node = checking.node_at(module session)
        printl(display.type_to_dewy(node.value_type session.types))
    }}
    let invalid:array<string> = [{errors}]
    loop text in invalid {{
        let source = SrcFile['fixture' text]
        let parsed = parser.parse(source)
        if parsed is? Error {{ parsed.fail return 1 }}
        let session = contexts.Session[]
        let lexical = contexts.begin(source parsed.nodes @session)
        let environment = checking.begin(lexical @session)
        let result = checking.block(parsed.root environment @session)
        $runtime_assert result is? Error
        $runtime_assert result.title not=? 'native checker implementation pending'
        $runtime_assert result.pointers.length >? 0 and result.pointers[0].message.length >? 0
        printl('rejected')
    }}
    return if failures =? 0 0 else 1
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert list(zip(CASES + ERROR_CASES, result.stdout.splitlines(), strict=True)) == list(zip(CASES + ERROR_CASES, expected + ['rejected'] * len(ERROR_CASES), strict=True))
