"""Literal shifts preserve high words until the exact result is narrowed."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_literal_multiword_shifts_roundtrip(compiler, tmp_path, release):
    shifts = [1, 31, 32, 63, 64, 65, 127]
    source = tmp_path / 'shifts.dewy'
    source.write_text(('\n'.join(f'f{s}=(x:int64):>int64=>(x << {s}) >> {s}' for s in shifts) + '''
main=(args:array<string>)=>{$runtime_checks\n
let x=int64(to_int(args[1]) ?? 0)
''' + '\n'.join(f'printl(f{s}(x))' for s in shifts) + '\n}\n') + "\n$runtime_checks\n")
    binary = tmp_path / 'shifts'
    built = subprocess.run([compiler, 'build', source, '-o', binary] + (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for x in [-2**63, -2**63+1, -1, 0, 1, 2**62, 2**63-1]:
        ran = subprocess.run([binary, str(x)], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.splitlines() == [str(x)] * len(shifts), ran.stdout + ran.stderr


@pytest.mark.parametrize('release', [False, True])
def test_dynamic_shift_keeps_high_words(compiler, tmp_path, release):
    source = tmp_path / 'dynamic.dewy'
    source.write_text('''
f=(x:int64 by:int64):>int64=>{
    $runtime_checks
    if by >=? 64 and by <=? 127 {return (x << 64) >> by}
    return 0
}
main=(args:array<string>)=>{$runtime_checks\nprintl(f(int64(to_int(args[1]) ?? 0) int64(to_int(args[2]) ?? 0)))}
''')
    binary = tmp_path / 'dynamic'
    built = subprocess.run([compiler, 'build', source, '-o', binary] + (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for x in [-2**63, -1, 0, 1, 2**63-1]:
        for by in [64, 65, 95, 127]:
            ran = subprocess.run([binary, str(x), str(by)], capture_output=True, text=True)
            assert ran.returncode == 0 and ran.stdout.strip() == str((x << 64) >> by), ran.stdout + ran.stderr
