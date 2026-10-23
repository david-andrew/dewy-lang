"""Line and capture limits: a line over 16 MiB is a FileError (skipped, so reading goes on),
capture stops a child past 64 MiB of output with a FileError, and the end stays none."""
import shutil
import subprocess
import sys

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

LIMIT = 16 << 20

LINES = '''main=()=>{
    let argv=args()
    if argv.length >? 1 {
        let opened=open_file(argv[1])
        if opened is? none exit(2)
        if opened is? Canceled exit(2)
        let f=opened
        loop true {
            let line=f.read_line()
            if line is? none break
            if line is? Canceled exit(3)
            if line is? FileError printl"error" else printl(line.length)
        }
        f.close()
        return
    }
    loop true {
        let line=read_line()
        if line is? none break
        if line is? Canceled exit(3)
        if line is? FileError printl"error" else printl(line.length)
    }
}
'''

CAPTURE = '''main=()=>{
    let small=capture("/bin/sh" ["-c" "head -c 1000 /dev/zero"])
    if small is? Output printl(small.stdout.length) else printl"failed"
    let flood=capture("/bin/sh" ["-c" "exec yes"])
    printl(flood is? FileError)
    let err_flood=capture("/bin/sh" ["-c" "exec yes 1>&2"])
    printl(err_flood is? FileError)
}
'''


def build(compiler, tmp_path, name, program):
    source = tmp_path / f'{name}.dewy'
    source.write_text(program)
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX pipes')
def test_line_limit(compiler, tmp_path):
    binary = build(compiler, tmp_path, 'lines', LINES)
    data = b'short\n' + b'x' * LIMIT + b'\r\n' + b'y' * (LIMIT + 1) + b'\nnext\n' + b'z' * (LIMIT + 5)
    expected = ['5', str(LIMIT), 'error', '4', 'error']
    ran = subprocess.run([binary], input=data, capture_output=True, timeout=60, check=False)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.decode().splitlines() == expected
    path = tmp_path / 'lines.txt'
    path.write_bytes(data)
    ran = subprocess.run([binary, path], capture_output=True, timeout=60, check=False)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.decode().splitlines() == expected


@pytest.mark.skipif(shutil.which('yes') is None or sys.platform == 'win32', reason='POSIX tools')
def test_capture_limit(compiler, tmp_path):
    binary = build(compiler, tmp_path, 'capture', CAPTURE)
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, check=False)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['1000', 'true', 'true']
