"""Scope labels and nonlocal exits retain the hosted control-flow contract."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import NotImplementedYet, UserError
from dewy.semantic import check
from tests.python_misc.test_bootstrap_lowering import ARENA, ROOT, build_native_lowering_driver
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

CASES = [
    # The module initializer is another independent runtime control boundary.
    """let answer:int64=0
    $outer
    loop true {loop true {answer=42 break $outer}}
    let main=():>int64=>answer""",
    (ROOT / 'dewy/tests/labeled_loop_exits.dewy').read_text(),
    # Scope-wide visibility, sibling reuse, and no attachment to one loop.
    '''let main=():>int64=>{
        let result:int64=0
        loop true {result+=20 break $later}
        loop true {result+=22 break $later}
        $later
        {$reused}
        {$reused}
        return result
    }''',
    # Two outward levels and a target continue must reset both signals.
    '''let main=():>int64=>{
        let i:int64=0
        let result:int64=0
        $outer
        loop i<?3 {
            i+=1
            loop true {
                loop true {
                    if i=?1 {result+=2 continue $outer}
                    result+=40
                    break $outer
                }
                result+=100
            }
            result+=100
        }
        return result
    }''',
    # Unbraced loops share the same parent label scope: nearest match wins.
    '''let main=():>int64=>{
        let i:int64=0
        $same
        loop i<?2 loop true {i+=1 break $same}
        return i+40
    }''',
    # A nested function may reuse its enclosing function's label spelling.
    '''let main=():>int64=>{
        $same
        let local=():>int64=>{$same loop true {break $same} return 42}
        return local()
    }''',
]
ERRORS = [
    'let main=():>void=>{$same $same}',
    'let main=():>void=>{{$same} $same}',
    'let main=():>void=>{loop true {break $missing}}',
    'let main=():>void=>{loop true {$inside break $inside}}',
    'let main=():>void=>{$outer loop true {let local=():>void=>{loop true {break $outer}} break}}',
    'let main=():>void=>{$label break $label}',
    'let main=():>void=>{$label let value=$label}',
]


def check_labeled_exits(binary, tmp_path):
    for index, text in enumerate(CASES):
        source = tmp_path / f'label-{index}.dewy'
        source.write_text(text)
        native = subprocess.run([binary, source], capture_output=True, text=True, timeout=30)
        assert native.returncode == 0, native.stdout + native.stderr
        for implementation, code in [('native', native.stdout),
                                     ('hosted', codegen(SrcFile.from_path(source), debug_locations=False))]:
            output = tmp_path / f'label-{index}-{implementation}.udewy'
            output.write_text(code)
            for target in ['x86_64', 'c']:
                assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=False, target=target)) == 0
                result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=10)
                assert result.returncode == 42, (index, implementation, target, result)
    for index, text in enumerate(ERRORS):
        source = tmp_path / f'label-error-{index}.dewy'
        source.write_text(text)
        with pytest.raises((UserError, NotImplementedYet)):
            check.typecheck_and_resolve(SrcFile.from_path(source))
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30)
        assert result.returncode != 0, text


def test_native_labeled_exits(tmp_path):
    binary = build_native_lowering_driver(tmp_path)
    check_labeled_exits(binary, tmp_path)
    source = tmp_path / 'cleanup.dewy'
    source.write_text(ARENA + (ROOT / 'tests/fixtures/native_labeled_exit_cleanup.dewy').read_text())
    native = subprocess.run([binary, source], capture_output=True, text=True, timeout=30)
    assert native.returncode == 0, native.stdout + native.stderr
    output = source.with_suffix('.udewy')
    output.write_text(native.stdout)
    # Storage costs need not match hosted lowering. Assert the native budget
    # independently, on both backends, rather than comparing two results.
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=False, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=10)
        assert result.returncode == 42, (target, result)
