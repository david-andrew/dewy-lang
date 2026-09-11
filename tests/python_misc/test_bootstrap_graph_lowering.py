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
        ({'entry.dewy': 'let combine=(left:int64 scale:int64=2 right:int64):>int64=>left+right*scale\nlet main=():>int64=>combine(scale=2 10 16)'}, 42),
        ({'entry.dewy': 'let combine=(left:int64 scale:int64=2 right:int64):>int64=>left+right*scale\nlet main=():>int64=>combine(right=16 10)'}, 42),
        ({'entry.dewy': 'let change=(value:int64 @target:int64):>void=>{target=value}\nlet main=():>int64=>{let x:int64=0 change(value=42 @x) return x}'}, 42),
        ({'entry.dewy': 'let choose=<T>(first:T second:T):>T=>first\nlet main=():>int64=>choose(second=0 42)'}, 42),
        ({'entry.dewy': 'let main=():>int64=>{let left:uint8=7 let right:int64=9 if left <? right return 42 return 1}'}, 42),
        ({'entry.dewy': 'let main=():>int64=>{let left:uint64=18446744073709551615 let right:int64=7 if left >? right return 42 return 1}'}, 42),
        ({'entry.dewy': 'let main=():>int64=>{let left:int64=-9223372036854775808 let right:uint64=7 if left <? right return 42 return 1}'}, 42),
        ({'entry.dewy': 'let compare=(value:addr limit:uint64<n => n <=? 281474976710655>):>bool=>{let length:addr?=value return if length isnt? none length >=? limit else false}\nlet main=():>int64=>if compare(1 2) 1 else 42'}, 42),
        ({'entry.dewy': 'let read=():>int64=>ANSWER\nconst ANSWER=42\nlet main=():>int64=>read()'}, 42),
        ({'entry.dewy': 'let outer=():>int64=>{let read=():>int64=>answer\nlet answer:int64=42\nreturn read()}\nlet main=():>int64=>outer()'}, 42),
        # Native HIR must retain a literal field as the subject of its proof.
        # This traverses a loop with a continue in obligations.field_subject.
        ({'entry.dewy': 'BigInt:type=0|[sign:-1|1 limbs:array<uint64 length >? 0>]\nlet main=():>int64=>{let one:BigInt<sign =? 1>=[sign=1 limbs=[1]] return one.sign+41}'}, 42),
        ({'entry.dewy': 'let main=():>int64=>{let position:addr|none=none loop i in 0.. and i <? 2 {position=i} return if position is? none 0 else position+41}'}, 42),
        ({'entry.dewy': 'let main=():>int64=>{let number:int64=42 let value:uint8|none=number return if value is? none 0 else value as int64}'}, 42),
        ({'entry.dewy': 'let main=():>int64=>{let number:uint8=42 let value:uint64|none=number return if value is? none 0 else if value =? 42 42 else 0}'}, 42),
        ({'entry.dewy': 'let count=(arity:addr):>int64=>{let n:int64=0 loop i in 0.. and i <? arity {n+=1} return n}\nlet main=():>int64=>count(2)+40'}, 42),

        ({
            'dependency.dewy': 'const s:(1 * Time)=1 transmute (1 * Time)\nconst ms=s/1000\nconst millisecond=ms\nconst minute=60*s',
            'entry.dewy': 'import p"dependency.dewy" as dependency\nlet main=():>int64=>42',
        }, 42),
        ({
            'entry.dewy': 'let identity=(x:int64 * Time):>int64 * Time=>x\nlet main=():>int64=>(identity(42 transmute (int64 * Time))) transmute int64',
        }, 42),

        ({
            'dependency.dewy': 'let unused=((x:int64):>array<int64>=>[x]) & ((x:bool):>array<bool>=>[x])',
            'entry.dewy': 'import p"dependency.dewy" as dependency\nlet main=():>int64=>42',
        }, 42),
        ({
            'dependency.dewy': 'let choose=((x:int64):>int64=>x+2) & ((x:bool):>int64=>if x 40 else 0)',
            'entry.dewy': 'import p"dependency.dewy" as dependency\nlet main=():>int64=>dependency.choose(dependency.choose(true))',
        }, 42),

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
        ('let main=():>int64=>{let left:uint8=7 let right:uint16=256 if left <? right return 1 return 0}', 'cannot prove this integer fits'),
        ('let main=():>int64=>{let left:uint64=7 let right:int64=-1 if left >? right return 1 return 0}', 'cannot prove this integer fits'),
        ('let compare=(left:int64 right:uint64):>bool=>left <? right', 'cannot prove this integer fits'),
        ('let read=():>int64=>answer\nread()\nlet answer:int64=42', 'before initialization'),
        ('let read=(value:int64):>int64=>{let narrow:uint8|none=value return 0}', 'cannot prove this integer fits'),
        ('let main=():>int64=>{let position:addr|none=-1 return 0}', 'refinement refuted'),
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
        'T:type=[x:int64 add=(left:int64 right:int64):>int64=>x+left+right]\nlet main=():>int64=>T[20].add(right=2 20)',
        'let format=(value:int64|none flag:bool|none):>string=>"{value}:{flag}"\nlet main=():>int64=>if format(none true)=?"none:true" and format(42 none)=?"42:none" 42 else 0',
        'let format=(value:int64|string|none):>string=>"{value}"\nlet main=():>int64=>if format(42)=?"42" and format("text")=?"text" and format(none)=?"none" 42 else 0',
        'let calls:int64=0\nlet next=():>int64|none=>{calls+=1 return calls}\nlet main=():>int64=>{let text="{next()}:{next()}" return if text=?"1:2" and calls=?2 42 else 0}',
        'let format=(record:[value:addr|none when:bool|none]):>string=>"{record.value}:{record.when}"\nlet main=():>int64=>if format([42 false])=?"42:false" and format([none none])=?"none:none" 42 else 0',
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
