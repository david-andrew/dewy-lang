"""Returns preserve the stack and unwind correctly after restoring rbp."""
import platform
import re
import shutil
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_return_paths_and_epilogue_unwind(compiler, tmp_path, flags):
    source = tmp_path / 'returns.jo'
    source.write_text('''@noinline
probe = (n: int) -> int:
    if n < 0: return -n
    xs = [n, n + 1, n + 2]
    xs[1] + n
@noinline
leaf = (a: int, b: int, c: int, d: int, e: int, f: int, g: int) -> int: a + g
@noinline
caller = () -> int: probe(-7) + probe(11) + leaf(4, 0, 0, 0, 0, 0, 1)
print(caller())
''')
    binary = tmp_path / 'returns'
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0 and ran.stdout == '35\n', ran.stdout + ran.stderr
    if flags != ['-g']:
        return
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        pytest.skip('x64 Linux unwind check')
    if not shutil.which('objdump') or not shutil.which('gdb'):
        pytest.skip('objdump and gdb required for epilogue unwind check')
    assembly = subprocess.check_output(['objdump', '-d', '--disassemble=probe', binary], text=True)
    returns = re.findall(r'^\s*([0-9a-f]+):\s+c3\s+ret', assembly, re.M)
    assert len(returns) >= 2, assembly
    leaf = subprocess.check_output(['objdump', '-d', '--disassemble=leaf', binary], text=True)
    leaf_returns = re.findall(r'^\s*([0-9a-f]+):\s+c3\s+ret', leaf, re.M)
    assert leaf_returns, leaf
    commands = tmp_path / 'returns.gdb'
    commands.write_text('set pagination off\n' + ''.join(
        f'break *0x{address}\ncommands\nsilent\nbacktrace\ncontinue\nend\n'
        for address in returns + leaf_returns) + 'run\n')
    debugged = subprocess.run(['gdb', '--batch', '-nx', '-x', commands, binary],
                              capture_output=True, text=True, timeout=30)
    assert debugged.returncode == 0, debugged.stdout + debugged.stderr
    # At ret, rbp already belongs to the caller. The epilogue CFI must still
    # recover caller's frame instead of skipping it or following a stale CFA.
    assert len(re.findall(r'#0\s+.*\bprobe\b', debugged.stdout)) == 2, debugged.stdout
    assert len(re.findall(r'#0\s+.*\bleaf\b', debugged.stdout)) == 1, debugged.stdout
    assert len(re.findall(r'#1\s+.*\bcaller\b', debugged.stdout)) == 3, debugged.stdout
