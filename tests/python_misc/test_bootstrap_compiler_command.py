"""The native Dewy command invokes a native µDewy executable directly."""
import os
import subprocess
from pathlib import Path

from test_bootstrap_lowering import ARENA

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.prelude import prelude_files
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_compiler_command(tmp_path):
    # Python supplies the initial Dewy text and µDewy seed; all command
    # invocations below execute the two native compilers, without a shim.
    micro_source = tmp_path / 'micro.udewy'
    micro_source.write_text(f'import p"{ROOT / "udewy/bootstrap/main.udewy"}"\n')
    assert entry_point(micro_source, [], EntryPointOptions(compile_only=True)) == 0
    micro = cache_artifact(micro_source).resolve()
    compiler_source = tmp_path / 'compiler.udewy'
    compiler_source.write_text(codegen(SrcFile.from_path(ROOT / 'dewy/bootstrap/main.dewy')))
    built = subprocess.run([micro, '-c', compiler_source], capture_output=True,
                           text=True, timeout=300, check=False)
    assert built.returncode == 0, f'µDewy exited {built.returncode}: {built.stdout}{built.stderr}'
    compiler = cache_artifact(compiler_source).resolve()

    # A small installed library tests the invocation boundary independently
    # of full-prelude parity. Its arena is the actual implementation.
    library = tmp_path / 'library'
    for path in prelude_files():
        copied = library / path.relative_to(ROOT / 'library')
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_text('')
    (library / 'linux/system.dewy').write_text(ARENA)
    env = dict(os.environ, DEWY_LIBRARY_ROOT=str(library), DEWY_UDEWY=str(micro))

    def invoke(*args):
        return subprocess.run([compiler, *args], cwd=tmp_path, env=env,
                              capture_output=True, text=True, timeout=120, check=False)

    assert invoke('--help').returncode == 0
    version = invoke('--version')
    assert version.returncode == 0 and version.stdout.startswith('dewy ')
    program = tmp_path / 'program.dewy'
    for body in [
        '$no_prelude=true\nlet main=():>int64=>42',
        'let main=():>int64=>{let values:array<int64>=[40 2] return values[0]+values[1]}',
        'let counter:int64=0\nlet read=(values:array<int64 length=1>):>int64=>{counter+=1 return values[0]}\nlet main=():>int64=>{let values:array<int64>=[42] let before=_arena_cursor let value=read(values) return if before =? _arena_cursor value else 0}',
        'let min=(a:int64 b:int64):>int64<v=>v <=? a and v <=? b>=>if a <? b a else b\nlet main=():>int64=>min(42 99)',
    ]:
        program.write_text(body)
        result = invoke(program)
        assert result.returncode == 42, result.stdout + result.stderr
        result = invoke('-c', program)
        assert result.returncode == 0, result.stdout + result.stderr
        assert (tmp_path / cache_artifact(program, cwd=tmp_path)).is_file()
    result = invoke('debug', '--build', program)
    assert result.returncode == 0, result.stdout + result.stderr
    assert Path(result.stdout.splitlines()[-1]).is_file()
    result = invoke('analyze', program)
    assert result.returncode == 0 and 'representation decisions' in result.stdout
    program.write_text('let main=(value:int64):>int64=>value')
    result = invoke(program)
    assert result.returncode != 0 and '`main` must take' in result.stderr

    # Minimal reporting hooks isolate runner generation and process statuses
    # from the full library's output capture implementation (tested separately).
    # This fixture accepts only ASCII arguments. Full Unicode segmentation is
    # exercised by the native runtime suite using the actual library tables.
    (library / 'unicode/runtime.dewy').write_text('''
let _utf8_boundaries=(bytes:array<uint8>):>array<int64>|none=>{
    let result:array<int64>=[0]
    loop i in 0.. and i <? bytes.length {
        if bytes[i] >=? 128 return none
        result.push(i+1)
    }
    return result
}
''')
    (library / 'io.dewy').write_text('let exit=(code:int64):>never=>{__syscall1__(231 code); __unreachable__()}')
    (library / 'testing.dewy').write_text('''
let begun:int64=0
let ended:int64=0
let _test_init=(json:bool):>void=>{begun=0 ended=0}
let _test_begin=(json:bool):>void=>{begun+=1}
let _test_end=(name:string case:int64 json:bool):>void=>{ended+=1}
let _test_summary=(json:bool brief:bool):>int64=>
    if begun =? 3 and ended =? 3 and json and brief 7 else 99
''')
    program.write_text('$test(cases=[1 2 3])\nlet check_case=(value:int64):>void=>{}')
    result = invoke('test', '--json', '--brief', program)
    assert result.returncode == 7, result.stdout + result.stderr
    # A backend compile failure is not a test's failure count.
    backend_failure = tmp_path / 'backend-failure'
    backend_failure.write_text('#!/bin/sh\nexit 17\n')
    backend_failure.chmod(0o755)
    env['DEWY_UDEWY'] = str(backend_failure)
    result = invoke('test', program)
    assert result.returncode == 102, result.stdout + result.stderr
    program.write_text('$test\nlet bad=(value:int64):>void=>{}')
    result = invoke('test', program)
    assert result.returncode == 102, result.stdout + result.stderr

    # Real numeric helpers must receive the present payload, while a missing
    # value stays none. The fixture's counter catches repeated source calls.
    numeric = subprocess.run(
        [compiler, ROOT / 'tests/fixtures/native_optional_bigint.dewy'],
        cwd=tmp_path,
        env=env | {'DEWY_LIBRARY_ROOT': str(ROOT / 'library'), 'DEWY_UDEWY': str(micro)},
        capture_output=True, text=True, timeout=900, check=False,
    )
    assert numeric.returncode == 42, numeric.stdout + numeric.stderr
    assert numeric.stdout == 'none|0|18446744073709551615|-9223372036854775808|4\n'

    nonzero = subprocess.run(
        [compiler, ROOT / 'tests/fixtures/native_nonzero_compound_bigint.dewy'],
        cwd=tmp_path,
        env=env | {'DEWY_LIBRARY_ROOT': str(ROOT / 'library'), 'DEWY_UDEWY': str(micro)},
        capture_output=True, text=True, timeout=900, check=False,
    )
    assert nonzero.returncode == 42, nonzero.stdout + nonzero.stderr
    assert nonzero.stdout == '42|11|42|4|2\n'
