"""Validate module proofs and startup before native graph legalization."""
import subprocess
from pathlib import Path

from test_bootstrap_lowering import ARENA

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_graph_initialization_and_entry(tmp_path):
    driver = tmp_path / 'graph.dewy'
    driver.write_text(f'''
from reporting import Error
import p"{ROOT / 'dewy/bootstrap/semantic/modules.dewy'}" as modules
import p"{ROOT / 'dewy/bootstrap/backend/udewy/graph.dewy'}" as graph
import p"{ROOT / 'dewy/bootstrap/backend/udewy/program.dewy'}" as program
main=(argv:array<string>):>int64=>{{
    $runtime_assert argv.length >=? 2
    let prelude:array<string>=[]
    loop i in 2.. and i <? argv.length {{prelude.push(argv[i])}}
    let engine=modules.Engine[prelude_files=prelude]
    let entry=modules.load(argv[1] @engine)
    if entry is? Error {{entry.fail}}
    let lowered=graph.lower_validated(entry @engine)
    if lowered is? Error {{lowered.fail}}
    let code=program.render(lowered.program lowered.input)
    if code is? Error {{code.fail}}
    printl(code)
    return 0
}}
''')
    seed = driver.with_suffix('.udewy')
    seed.write_text(codegen(SrcFile.from_path(driver)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    binary = cache_artifact(seed).resolve()
    cases = [
        ({
            'core.dewy': 'let count:int64=0\nlet tick=():>int64=>{count+=1 return count}',
            'left.dewy': 'import p"core.dewy" as core\nlet value:int64=core.tick()',
            'right.dewy': 'import p"./core.dewy" as core\nlet value:int64=core.tick()',
            'entry.dewy': 'import p"left.dewy" as left\nimport p"right.dewy" as right\nimport p"core.dewy" as core\nlet main=():>int64=>left.value+right.value+core.count+37',
        }, 42),
        ({
            'dependency.dewy': 'let main=():>int64=>99\nlet initialized:int64=main()',
            'entry.dewy': 'import p"dependency.dewy" as dependency\nlet value=dependency.initialized',
        }, 0),
        ({
            'left.dewy': 'let answer=():>int64=>20',
            'right.dewy': 'let answer=():>int64=>22',
            'entry.dewy': 'import p"left.dewy" as left\nimport p"right.dewy" as right\nlet main=():>int64=>left.answer()+right.answer()',
        }, 42),
        ({
            'dependency.dewy': 'let unused=():>array<int64>=>[1 2]',
            'entry.dewy': 'import p"dependency.dewy" as dependency\nlet main=():>int64=>42',
        }, 42),
        ({
            'entry.dewy': 'let main=():>int64=>{let bytes:array<uint8>=[42] return bytes[0] as int64}',
        }, 42),
    ]
    for index, (files, expected) in enumerate(cases):
        folder = tmp_path / f'case-{index}'
        folder.mkdir()
        for name, text in files.items():
            (folder / name).write_text(text)
        result = subprocess.run([binary, folder / 'entry.dewy'], capture_output=True, text=True, timeout=60, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        output = folder / 'program.udewy'
        output.write_text(result.stdout)
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], timeout=10, check=False)
        assert run.returncode == expected
    bad = tmp_path / 'bad'
    bad.mkdir()
    (bad / 'dependency.dewy').write_text('let make=():>array<int64>=>[1 2]\nlet value=make()')
    (bad / 'entry.dewy').write_text('import p"dependency.dewy" as dependency\nlet main=():>int64=>42')
    result = subprocess.run([binary, bad / 'entry.dewy'], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode != 0
    assert str(bad / 'dependency.dewy') in result.stderr

    for index, (body, title) in enumerate([
        ('let f=(n:int64):>int64=>{ $assert n >? 0\nreturn n }', 'cannot prove assertion'),
        ('let main=(n:int64):>int64=>n', '`main` must take no arguments'),
        ('let x:int=9223372036854775807\nlet main=():>int=>x+1', 'cannot prove this integer fits'),
        ('let read=(values:array<uint64 length=1>):>int64=>values[0] as int64\nlet main=():>int64=>read([18446744073709551615])', 'cannot prove this integer fits'),
        ('call(); let call=():>int64=>42', 'before'),
    ]):
        path = tmp_path / f'rejected-{index}.dewy'
        path.write_text(body)
        result = subprocess.run([binary, path], capture_output=True, text=True, timeout=60, check=False)
        assert result.returncode != 0, body
        assert title in result.stderr, result.stdout + result.stderr

    # A small reporting prelude checks the compiler/library boundary without
    # depending on every operation used by the full diagnostic renderer yet.
    reporting = tmp_path / 'runtime-reporting.dewy'
    reporting.write_text(ARENA + '''
Path:type=[path:string]
let p=(path:string):>Path=>[path=path]
Report:type=[start:int64 stop:int64 dim_stop:int64 message:string]
let _assertion_report=(start:addr stop:addr dim_stop:addr message:string):>Report=>[start stop dim_stop message]
let _expectation_report=(start:addr stop:addr dim_stop:addr message:string):>Report=>[start stop dim_stop message]
let write=(text:string):>void=>{
    let bytes=text as array<uint8>
    __syscall3__(1 2 __load_i64__(bytes) bytes.length);
}
let _assertion_render=(report:Report path:string row:int64 line:string):>void=>{write(report.message);}
let _expect_failed=():>void=>{}
let exit=(code:int64):>never=>{__syscall1__(60 code); __unreachable__()}
''')
    for index, (value, expected, stderr) in enumerate([(0, 101, 'once:failed'), (1, 42, '')]):
        source = tmp_path / f'runtime-assert-{index}.dewy'
        source.write_text(f'''
let positive=(n:int64):>bool=>n>?0
let message=():>string=>{{write('once:'); return 'failed'}}
let exit=(code:int64):>int64=>77
let main=():>int64=>{{
    $runtime_assert positive({value}), message()
    return 42
}}
''')
        lowered = subprocess.run([binary, source, reporting], capture_output=True, text=True, timeout=90, check=False)
        assert lowered.returncode == 0, lowered.stdout + lowered.stderr
        output = source.with_suffix('.udewy')
        output.write_text(lowered.stdout)
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10, check=False)
        assert run.returncode == expected, run.stdout + run.stderr
        assert run.stderr == stderr

    unicode_runtime = ROOT / 'library/unicode/runtime.dewy'
    for index, body in enumerate([
        'let combine=(left:string right:string):>string=>left+right\nlet main=():>int64=>{let joined=combine("e" "\\u0301x") return if joined.length=?2 and joined[0]=?"é" 42 else 0}',
        'let decode=(bytes:array<uint8>):>string|none=>bytes as string|none\nlet main=():>int64=>{let text=decode([0x68 0xc3 0xa9]) return if text is? string and text=?"hé" and text.length=?2 42 else 0}',
        'let decode=(bytes:array<uint8>):>string|none=>bytes as string|none\nlet main=():>int64=>{let bad=decode([0xed 0xa0 0x80]) let empty=decode([]) return if bad is? none and empty is? string and empty.length=?0 42 else 0}',
        'let main=():>int64=>{let bytes:array<uint8>=[0x61] let text=bytes as string|none bytes[0]=0x7a return if text is? string and text=?"a" 42 else 0}',
        'let format=(number:uint64 small:int8 flag:bool):>string=>"{number}:{small}:{flag}"\nlet main=():>int64=>{let text=format(18446744073709551615 (-128) false) return if text=?"18446744073709551615:-128:false" 42 else 0}',
        'let format=(number:int64):>string=>"{number}"\nlet main=():>int64=>{return if format(-9223372036854775808)=?"-9223372036854775808" and format(0)=?"0" 42 else 0}',
        'let combine=(first:string last:string):>string=>"{first}{last}"\nlet main=():>int64=>{let text=combine("e" "\\u0301x") return if text.length=?2 42 else 0}',
        'let combine=(words:array<string> sep:string):>string=>words.join(sep)\nlet main=():>int64=>{let text=combine(["a" "b" "c"] "/") let empty=combine([] "/") return if text=?"a/b/c" and empty=?"" 42 else 0}',
        'let main=():>int64=>{let parts:array<string>=["e" "\\u0301x"] let text=parts.join return if text.length=?2 and text[0]=?"é" 42 else 0}',
    ]):
        source = tmp_path / f'unicode-runtime-{index}.dewy'
        source.write_text(body)
        lowered = subprocess.run([binary, source, reporting, unicode_runtime], capture_output=True, text=True, timeout=120, check=False)
        assert lowered.returncode == 0, lowered.stdout + lowered.stderr
        output = source.with_suffix('.udewy')
        output.write_text(lowered.stdout)
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=15, check=False)
        assert run.returncode == 42, run.stdout + run.stderr

    source = tmp_path / 'command-line.dewy'
    source.write_text('let initialized:int64=41\nlet main=(argv:array<string>):>int64=>{if argv.length=?4 and argv[1]=?"a" and argv[2].length=?1 and argv[3]=?"" return initialized+1 return 0}')
    lowered = subprocess.run([binary, source, reporting, unicode_runtime], capture_output=True, text=True, timeout=120, check=False)
    assert lowered.returncode == 0, lowered.stdout + lowered.stderr
    output = source.with_suffix('.udewy')
    output.write_text(lowered.stdout)
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    executable = cache_artifact(output).resolve()
    run = subprocess.run([executable, 'a', 'é', ''], capture_output=True, text=True, timeout=15, check=False)
    assert run.returncode == 42, run.stdout + run.stderr
    invalid = subprocess.run([bytes(executable), b'\xff'], capture_output=True, timeout=15, check=False)
    assert invalid.returncode == 1, invalid.stdout + invalid.stderr
