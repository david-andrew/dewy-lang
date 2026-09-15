"""Container text uses the source library and preserves evaluation order."""
import subprocess

import pytest

import test_bootstrap_lowering as native_lowering
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import TypeCheckError, UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


CASES = [
    'let main=():>int64=>{let xs:array<int64>=[1 2 3] return if (xs as string)=?"[1 2 3]" 42 else 0}',
    '''let main=():>int64=>{let xs:array<string>=["aa" "b\\tc"] return if (xs as string)=?'["aa" "b\\\\tc"]' 42 else 0}''',
    '''let main=():>int64=>{let xs:set<string>=set["aa" "bb"] return if (xs as string)=?'set["aa" "bb"]' 42 else 0}''',
    '''let main=():>int64=>{let xs:dict<string int64>=["aa" -> 1 "bb" -> 2] return if (xs as string)=?'["aa" -> 1 "bb" -> 2]' 42 else 0}''',
    '''let main=():>int64=>{let xs:array<string|none>=[none "aa"] return if (xs as string)=?'[none "aa"]' 42 else 0}''',
    '''let main=():>int64=>{let xs:array<int64|string|none>=[1 "aa" none] return if "{xs}"=?'[1 "aa" none]' 42 else 0}''',
    'let main=():>int64=>{let xs:array<int64>=[] let ys:set<int64>=set[] let zs:dict<int64 int64>=[] return if "{xs}{ys}{zs}"=?"[]set[][]" 42 else 0}',
    'let calls:int64=0\nlet next=():>int64|none=>{calls+=1 return if calls=?1 none else calls}\nlet main=():>int64=>{let text="{next()}:{next()}" return if text=?"none:2" and calls=?2 42 else 0}',
    'let convert=(value:int64|none):>string=>value as string\nlet main=():>int64=>if convert(none)=?"none" and convert(42)=?"42" 42 else 0',
    (native_lowering.ROOT / 'tests/fixtures/union_string_tests.dewy').read_text(),
]
ERRORS = [
    'let main=():>int64=>{let xs:array<array<int64>>=[[1]] let text=xs as string return 0}',
    'let main=():>int64=>{let xs:array<uint8>=[255] let text=xs as string return 0}',
    '7 as string',
    'true as string',
]


def build_program_driver(tmp_path):
    output = tmp_path / 'program-driver.udewy'
    output.write_text(codegen(SrcFile.from_path(native_lowering.ROOT / 'tests/fixtures/bootstrap_program.dewy'), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=False)) == 0
    return cache_artifact(output).resolve()


def check_structural_text(binary, tmp_path, *, cases=None, errors=None):
    cases = CASES if cases is None else cases
    errors = ERRORS if errors is None else errors
    def compile_native(source):
        return subprocess.run([binary, source, native_lowering.ROOT / 'library', tmp_path / 'prelude-cache'], capture_output=True, text=True, timeout=120)

    for index, text in enumerate(cases):
        source = tmp_path / f'case-{index}.dewy'
        source.write_text(text)
        compiled = compile_native(source)
        assert compiled.returncode == 0, text + '\n' + compiled.stdout + compiled.stderr
        hosted = codegen(SrcFile.from_path(source), debug_locations=False)
        for implementation, emitted in [('native', compiled.stdout), ('hosted', hosted)]:
            output = tmp_path / f'{implementation}-{index}.udewy'
            output.write_text(emitted)
            for target in ('x86_64', 'c'):
                assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
                result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=10)
                assert result.returncode == 42, (implementation, target, text, result)
    for index, text in enumerate(errors):
        source = tmp_path / f'error-{index}.dewy'
        source.write_text(text)
        with pytest.raises((TypeCheckError, UserError)):
            codegen(SrcFile.from_path(source), debug_locations=False)
        result = compile_native(source)
        assert result.returncode == 1 and 'Error' in result.stderr, (text, result.returncode, result.stderr)


def test_native_structural_text(tmp_path):
    check_structural_text(build_program_driver(tmp_path), tmp_path)
