"""gdb and lldb show Dewy values as Dewy prints them (lib/debug)."""
import platform
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SOURCE = '''Hit:type = [length:int64 name:string]
Node:type = [value:int64 next:Node?=none]
probe = (hits:array<Hit> label:string) => {
    let n:int = 42
    let big:int = -123456789012345678901234567890
    let xs:array<int64> = [1 2 3]
    let maybe:int64? = none
    let u:int64|string = "x"
    let d = ["a"->1 "b"->2]
    let node = Node[20 Node[22]]
    printl(n + big + xs[0] + (maybe ?? 0) + d["a"] + node.value)
    printl(u)
}
main = () => probe([Hit(3 "a") Hit(10 "b")] "run")
'''

EXPECTED = ['hits = [[length=3 name="a"] [length=10 name="b"]]', 'label = "run"', 'n = 42',
            'big = -123456789012345678901234567890', 'xs = [1 2 3]', 'maybe = none', 'u = "x"',
            'd = ["a" -> 1 "b" -> 2]', 'node = [value=20 next=[value=22 next=none]]']


def build(compiler, tmp_path):  # noqa: F811
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        pytest.skip('native Linux x86-64 required')
    source = tmp_path / 'probe.dewy'
    source.write_text(SOURCE)
    binary = tmp_path / 'probe'
    built = subprocess.run([compiler, 'build', source, '-g', '-o', binary], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    return source, binary


def test_gdb_printers(compiler, tmp_path):  # noqa: F811
    if not shutil.which('gdb'):
        pytest.skip('gdb required')
    source, binary = build(compiler, tmp_path)
    printer = compiler.parent.parent / 'lib/debug/dewy_gdb.py'
    ran = subprocess.run(['gdb', '--batch', '-nx', '-ex', f'source {printer}', '-ex', f'break {source}:11',
                          '-ex', 'run', '-ex', 'info args', '-ex', 'info locals', str(binary)],
                         capture_output=True, text=True, timeout=60)
    for line in EXPECTED:
        assert line in ran.stdout, ran.stdout + ran.stderr


def test_lldb_printers(compiler, tmp_path):  # noqa: F811
    if not shutil.which('lldb'):
        pytest.skip('lldb required')
    source, binary = build(compiler, tmp_path)
    printer = compiler.parent.parent / 'lib/debug/dewy_lldb.py'
    ran = subprocess.run(['lldb', '--batch', '-o', f'command script import {printer}', '-o', f'b {source}:11',
                          '-o', 'run', '-o', 'frame variable', str(binary)],
                         capture_output=True, text=True, timeout=120)
    for line in EXPECTED:
        assert line in ran.stdout, ran.stdout + ran.stderr
    assert '(int) n = 42' in ran.stdout and '(array<int64>) xs = [1 2 3]' in ran.stdout, ran.stdout
