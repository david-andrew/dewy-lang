"""Debug info lists a Dewy function's value parameters once, as its formal parameters."""
import platform
import re
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (the fixture)

SOURCE = '''$runtime_checks
probe=(n:int64 @acc:int64 k:int64):>int64=>{
k = k + 1
acc = acc + n
let total=n+k
printl"{total} {acc}"
return total
}
main=():>void=>exit(entry())
entry=()=>{
let a:int64=5
return probe(20 @a 21)
}
'''


def build(compiler, tmp_path, *target):
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    binary = tmp_path / ('program.exe' if target else 'program')
    built = subprocess.run([compiler, 'build', source, '-g', *target, '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    return source, binary


def test_gdb_value_parameters(compiler, tmp_path):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or not shutil.which('gdb'):
        pytest.skip('native Linux x86-64 with GDB required')
    source, binary = build(compiler, tmp_path)
    debugged = subprocess.run([
        'gdb', '--batch', '-nx', '-ex', f'break {source}:6', '-ex', 'run',
        '-ex', 'info args', '-ex', 'echo --locals--\\n', '-ex', 'info locals', str(binary),
    ], capture_output=True, text=True, timeout=60, check=False)
    assert debugged.returncode == 0, debugged.stdout + debugged.stderr
    args, local_vars = debugged.stdout.split('--locals--\n')
    # (in source order, once each: the reassigned k with its value now)
    assert re.findall(r'^(\w+) = (\d+)$', args, re.M)[-3:] == [('n', '20'), ('acc', '25'), ('k', '22')], args
    assert re.findall(r'^(\w+) = ', local_vars, re.M) == ['total'], local_vars


def test_pdb_value_parameters(compiler, tmp_path):
    if not shutil.which('llvm-pdbutil'):
        pytest.skip('llvm-pdbutil required')
    _, binary = build(compiler, tmp_path, '--target', 'x86_64-windows')
    dumped = subprocess.run(['llvm-pdbutil', 'dump', '--symbols', binary.with_suffix('.pdb')],
                            capture_output=True, text=True, timeout=60, check=False)
    assert dumped.returncode == 0, dumped.stdout + dumped.stderr
    probe = dumped.stdout.split('`probe`', 1)[1].split('S_GPROC32', 1)[0]
    found = re.findall(r'S_LOCAL \[size = \d+\] `(\w+)`\s+type=[^,]*, flags = (\w+)', probe)
    assert found == [('n', 'param'), ('acc', 'param'), ('k', 'param'), ('total', 'none')], probe
