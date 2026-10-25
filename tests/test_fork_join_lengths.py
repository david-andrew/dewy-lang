"""Fixed fork collectors keep their length even when no array is materialized."""
import os
import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler, target_name


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('count', [2, 5, 8])
def test_length_and_ordered_results(compiler, tmp_path, target, count):
    source = tmp_path / 'lengths.dewy'
    source.write_text('''
work=(n:int64):>int64=>{
 if n <? 1 return 1
 let parts=[parallel i in [3..END) work(n-1)+i]
 $runtime_assert parts.length =? COUNT
 return parts[0]-parts[1]+parts[LAST]+parts.length
}
main=()=>{printl"{work(5)}"}
$runtime_checks
'''.replace('END', str(3+count)).replace('COUNT', str(count)).replace('LAST', str(count-1)))
    binary = tmp_path / 'lengths'
    built = subprocess.run([compiler, 'build', source, '--release', '--target', target_name(target),
                            '-o', binary], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    # Each level adds (-1 + (count+2) + count), independently of scheduling.
    expected = f'{1 + 5*(2*count+1)}\n'
    command = [binary]
    workers = (1, 2, 4)
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = binary.with_suffix('.cjs')
        runner.write_text('\n'.join(scripts.parts))
        command = [shutil.which('node'), runner]
        workers = (1,)
    for n in workers:
        result = subprocess.run(command, env=dict(os.environ, DEWY_THREADS=str(n)),
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected


def test_length_assertion_diagnostic(compiler, tmp_path):
    source = tmp_path / 'failure.dewy'
    source.write_text('''
main=()=>{
 let parts=[parallel i in [0..2) i+10]
 $runtime_assert parts.length =? 3
 printl"{parts[0]} {parts[1]}"
}
$runtime_checks
''')
    binary = tmp_path / 'failure'
    built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    for n in (1, 4):
        result = subprocess.run([binary], env=dict(os.environ, DEWY_THREADS=str(n)),
                                capture_output=True, text=True, timeout=20)
        assert result.returncode != 0
        assert 'assertion failed: parts.length =? 3' in result.stderr


def test_length_only_still_evaluates_children(compiler, tmp_path):
    source = tmp_path / 'length_only.dewy'
    source.write_text('''
work=(i:int64):>int64=>{
 if i =? 1 panic("length-only child ran")
 return i
}
main=()=>{
 let parts=[parallel i in [0..2) work(i)]
 printl"{parts.length}"
}
$runtime_checks
''')
    binary = tmp_path / 'length_only'
    built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    for n in (1, 4):
        result = subprocess.run([binary], env=dict(os.environ, DEWY_THREADS=str(n)),
                                capture_output=True, text=True, timeout=20)
        assert result.returncode != 0
        assert 'length-only child ran' in result.stderr
