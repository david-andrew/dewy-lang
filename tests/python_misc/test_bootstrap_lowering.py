"""The first native storage/legalization slice executes checked scalar programs.

This deliberately enters below the full validation driver; it is not a public
compiler command and does not authorize arbitrary unchecked source emission.
"""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ('let main=():>int64=>42', 42),
    ('let score:int64=40\nlet main=():>int64=>score+2', 42),
    ('let main=():>int64=>twice(21)\nlet twice=(x:int64):>int64=>x*2', 42),
    ('let x:int64=4\nlet main=():>int64=>{let x:int64=40\nx+=2\nreturn x}', 42),
    ('let f=(x:int64):>int64=>{if x >? 0 return 42\nreturn 9}\nlet main=():>int64=>f(1)', 42),
    ('let main=():>int64=>{let i:int64=0\nloop i <? 42 {i+=1}\nreturn i}', 42),
    ('let main=():>int64=>{let x:uint8=250\nx+=48\nreturn x as int64}', 42),
    ('let main=():>int64=>{let x:int64=63\nx and=42\nreturn x}', 42),
]


def test_native_scalar_lowering(tmp_path):
    source = tmp_path / 'lowering.dewy'
    source.write_text(f'''
from reporting import SrcFile, Error
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/check.dewy'}" as checking
import p"{ROOT / 'dewy/bootstrap/backend/udewy/emit.dewy'}" as emit
import p"{ROOT / 'dewy/bootstrap/backend/udewy/lower.dewy'}" as lower
import p"{ROOT / 'dewy/bootstrap/backend/udewy/program.dewy'}" as program
main = (argv:array<string>):>int64 => {{
    $runtime_assert argv.length =? 2
    let text=p(argv[1]).read_text
    if text isnt? string return 1
    let source=SrcFile[argv[1] text]
    let parsed=parser.parse(source)
    if parsed is? Error {{parsed.fail}}
    let session=contexts.Session[]
    let lexical=contexts.begin(source parsed.nodes @session)
    let env=checking.begin(lexical @session)
    let root=checking.module(parsed.root env @session)
    if root is? Error {{root.fail}}
    let lowered=lower.lower(root emit.Input[session.hir session.types] source)
    if lowered is? Error {{lowered.fail}}
    let code=program.render(lowered.program lowered.input)
    if code is? Error {{code.fail}}
    printl(code)
    return 0
}}
''')
    seed = source.with_suffix('.udewy')
    seed.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(seed).resolve()
    for index, (text, expected_exit) in enumerate(CASES):
        case = tmp_path / f'case-{index}.dewy'
        case.write_text(text)
        native = subprocess.run([binary, case], capture_output=True, text=True, timeout=60, check=False)
        assert native.returncode == 0, native.stdout + native.stderr
        output = case.with_suffix('.udewy')
        output.write_text(native.stdout)
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], timeout=10, check=False)
        assert result.returncode == expected_exit, text
