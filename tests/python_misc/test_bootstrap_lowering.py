"""Native storage/legalization executes scalar and local array programs.

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
    ('let main=():>int64=>{let values:array<int64>=[20 22] return values[0]+values[1]}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40 2] let copy=values copy[0]=99 return values[0]+copy[1]}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40 2] let copy:array<int64>=[0 0] copy=values copy[0]=99 return values[0]+copy[1]}', 42),
    ('let main=():>int64=>{let values:array<bool>=[false true] values[0]=values[1] return if values[0] and values[1] 42 else 0}', 42),
    ('let main=():>int64=>{let values:array<uint8>=[250 48] return (values[0]+values[1]) as int64}', 42),
    ('let main=():>int64=>{let values:array<int64>=[] return values.length+42}', 42),
    ('let main=():>int64=>{let values:array<int64>=[40 2] values=values return values[0]+values[1]}', 42),
    ('let main=():>int64=>{let memory=__alloca__(8) __store_i64__(42 memory) return __load_i64__(memory)}', 42),
    ('Fn:type=(x:int64):>int64\nlet twice=(x:int64):>int64=>x*2\nlet apply=(f:Fn=@twice):>int64=>f(21)\nlet main=():>int64=>apply()', 42),

    ('let f=(flag:bool=true):>int64=>if flag 42 else 0\nlet main=():>int64=>f()', 42),
    ('let seed:int64=0\nlet tick=():>bool=>{seed+=1 return seed <? 4}\nlet main=():>int64=>{loop tick() {} return seed+38}', 42),
    ('let seed:int64=0\nlet tick=():>bool=>{seed+=1 return false}\nlet main=():>int64=>{loop tick() {} else {seed+=41} return seed}', 42),
    ('let seed:int64=0\nlet tick=():>bool=>{seed+=1 return true}\nlet f=(flag:bool):>bool=>flag and tick()\nlet main=():>int64=>{f(false); f(true); return seed+41}', 42),
    ('let seed:int64=0\nlet tick=():>bool=>{seed+=1 return true}\nlet f=(flag:bool):>bool=>flag nor tick()\nlet main=():>int64=>{f(true); f(false); return seed+41}', 42),

    ('Fn:type=(x:int64):>int64\nlet apply=(f:Fn x:int64):>int64=>f(x)\nlet twice=(x:int64):>int64=>x*2\nlet main=():>int64=>apply(@twice 21)', 42),
    ('let add=(x:int64 y:int64=2):>int64=>x+y\nlet main=():>int64=>add(40)', 42),
    ('let add=(x:int64 y:int64=9):>int64=>x+y\nlet main=():>int64=>add(y=2 x=40)', 42),
    ('let combine=(left:int64 scale:int64=2 right:int64):>int64=>left+right*scale\nlet main=():>int64=>combine(10 right=16)', 42),
    ('let seed:int64=0\nlet next=():>int64=>{seed+=1 return seed}\nlet choose=(x:int64=next()):>int64=>x\nlet main=():>int64=>{choose(99); choose(); choose(); return seed+40}', 42),
    ('let seed:int64=0\nlet next=():>int64=>{seed+=1 return seed}\nlet difference=(x:int64 y:int64):>int64=>x-y\nlet main=():>int64=>difference(y=next() x=next())+41', 42),

    ('', 0),
    ('Word:type=int64\nlet main=():>Word=>42', 42),
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
