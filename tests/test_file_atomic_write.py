"""write_text and write_bytes replace a file in one step (a new file beside it, synced, renamed
over it), keep its permissions, and refuse a symbolic link rather than write through it."""
import os
import subprocess
import sys

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

# (programs that keep runtime checks for their unproven obligations)
RUNTIME_CHECKS = '\n$runtime_checks\n'

PROGRAM = '''main=()=>{
    let dir=args()[1]
    printl(write_text("{dir}/a.txt" "one"))
    printl(write_text("{dir}/a.txt" "two"))
    printl(write_text("{dir}/link.txt" "via link"))
    printl(write_text("{dir}/dangling.txt" "via link"))
    printl(write_text("{dir}/sub" "x"))
    printl(write_text("{dir}/missing/x" "x"))
    printl(write_text("{dir}/tool.sh" "#!/bin/sh"))
    printl(p"{dir}/b.bin".write_bytes([1 2 3]))
    printl(write_text("/dev/null" "gone"))
}
'''


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX links and permission bits')
def test_atomic_replace(compiler, tmp_path):
    source = tmp_path / 'write.dewy'
    source.write_text(PROGRAM + RUNTIME_CHECKS)
    binary = tmp_path / 'write'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'sub').mkdir()
    (work / 'target.txt').write_text('old')
    os.symlink('target.txt', work / 'link.txt')
    os.symlink('nowhere.txt', work / 'dangling.txt')
    (work / 'tool.sh').write_text('x')
    os.chmod(work / 'tool.sh', 0o750)
    ran = subprocess.run([binary, work], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['3', '3', 'FileError', 'FileError', 'IsDirectory', 'FileNotFound',
                                       '9', '3', '4']
    assert (work / 'a.txt').read_text() == 'two'
    assert (work / 'target.txt').read_text() == 'old'
    assert os.path.islink(work / 'link.txt') and os.path.islink(work / 'dangling.txt')
    assert not (work / 'nowhere.txt').exists()
    assert (work / 'tool.sh').read_text() == '#!/bin/sh'
    assert os.stat(work / 'tool.sh').st_mode & 0o777 == 0o750
    assert (work / 'b.bin').read_bytes() == b'\x01\x02\x03'
    assert sorted(p.name for p in work.iterdir()) == ['a.txt', 'b.bin', 'dangling.txt', 'link.txt', 'sub',
                                                      'target.txt', 'tool.sh']
