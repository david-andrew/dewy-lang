"""Version affine storage checks without changing the checked fallback."""
import platform
import re
import subprocess

import pytest

from tests.support import compiler


def compile_source(compiler, tmp_path, text, release):
    source = tmp_path / 'affine.dewy'
    source.write_text(text)
    binary = tmp_path / 'affine'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary, built.stdout


@pytest.mark.parametrize('release', [False, True])
def test_exact_affine_index_vectors(compiler, tmp_path, release):
    binary, ir = compile_source(compiler, tmp_path, '''
kernel=(xs:array<int64> shift:int64):>int64<overflow='wrap'>=>{
    $runtime_checks
    let total:int64<overflow='wrap'>=0
    loop i in [int64(0)..int64(32)) {total+=xs[i+shift]}
    return total
}
main=(args:array<string>)=>{
    let xs:array<int64>=[loop i in [0..34) i]
    printl(kernel(xs int64(to_int(args[1]) ?? 0)))
}
''', release)
    kernel = next((body for body in re.split(r'^fn ', ir, flags=re.MULTILINE)
                   if body.startswith('f_kernel_')), ir)
    if platform.machine().lower() in ('x86_64', 'amd64'):
        assert ' = vld ' in kernel, kernel
        assert 'checked_add ' in kernel, kernel
    for offset in [0, 1, 2]:
        ran = subprocess.run([binary, str(offset)], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.strip() == str(sum(range(offset, offset+32))), ran.stderr
    for offset in [-1, 3, 2**63-1, -2**63]:
        ran = subprocess.run([binary, str(offset)], capture_output=True, text=True)
        assert ran.returncode != 0 and not ran.stdout


def test_affine_fallback_keeps_failure_order(compiler, tmp_path):
    binary, ir = compile_source(compiler, tmp_path, '''
kernel=(@xs:array<int64> offset:int64)=>{
    $runtime_checks
    loop i in [int64(0)..int64(4)) {
        printl(i)
        xs[i]=i+offset
    }
}
main=(args:array<string>)=>{
    let xs:array<int64>=[0 0 0 0]
    kernel(@xs int64(to_int(args[1]) ?? 0))
}
''', True)
    ran = subprocess.run([binary, str(2**63-2)], capture_output=True, text=True)
    assert ran.returncode != 0
    assert ran.stdout.splitlines() == ['0', '1', '2']


def test_affine_intermediate_still_checks(compiler, tmp_path):
    binary, ir = compile_source(compiler, tmp_path, '''
kernel=(xs:array<int64> offset:int64):>int64<overflow='wrap'>=>{
    $runtime_checks
    let total:int64<overflow='wrap'>=0
    loop i in [int64(0)..int64(4)) {
        let j:int64=i+offset
        total+=xs[j-offset]
    }
    return total
}
main=(args:array<string>)=>{
    let xs:array<int64>=[1 2 3 4]
    printl(kernel(xs int64(to_int(args[1]) ?? 0)))
}
''', True)
    ran = subprocess.run([binary, '0'], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout.strip() == '10', ran.stderr
    ran = subprocess.run([binary, str(2**63-1)], capture_output=True, text=True)
    assert ran.returncode != 0 and not ran.stdout
