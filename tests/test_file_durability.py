"""Provisional durability operations on paths: sync, atomic replace, binary append, positional read."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROGRAM = r'''
let dir=p"store"
dir.mkdir
let log=p"store/log"
printl(log.write_bytes([1 2 3]))
printl(log.append_bytes([4 5 0 255]))
printl(log.sync)
printl(dir.sync)
printl(log.read_at(2 3))
printl(log.read_at(5 10))
printl(log.read_at(40 2))
printl(log.read_at(-1 2) is? FileError)
let next=p"store/MANIFEST.tmp"
next.write_text("generation 2\n")
next.sync
printl(next.replace(p"store/MANIFEST"))
dir.sync
printl(p"store/MANIFEST".read_text)
printl(next.exists)
printl(p"store/missing".sync is? FileNotFound)
printl(p"store/missing".read_at(0 1) is? FileNotFound)
printl(p"store/missing".replace(p"store/x") is? FileNotFound)
printl(p"store/none/log".append_bytes([1]) is? FileNotFound)
printl(dir.read_at(0 1) is? IsDirectory)
'''

EXPECTED = '''3
4
true
true
[3 4 5]
[0 255]
[]
true
true
generation 2

false
true
true
true
true
true
'''


@pytest.mark.parametrize('mode', ['default', 'release'])
def test_file_durability(compiler, tmp_path, mode):
    source = tmp_path / 'durable.dewy'
    source.write_text(PROGRAM)
    binary = tmp_path / 'durable'
    args = [compiler, 'build', source, '-o', binary] + (['--release'] if mode == 'release' else [])
    built = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, cwd=tmp_path)
    assert (ran.returncode, ran.stdout) == (0, EXPECTED), ran.stderr
    assert (tmp_path / 'store/log').read_bytes() == bytes([1, 2, 3, 4, 5, 0, 255])
