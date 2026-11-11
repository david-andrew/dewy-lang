"""`ptr<T>?` is one word in memory, C's nullable pointer: C fills `T **` out-parameters, arrays of
nullable pointers and record fields in place, and `none` and pointers round-trip through records,
arrays, unions, results and callbacks. Native x86-64 in each build mode, and aarch64-linux in the
sloppy-arm64 container against the library cross-built with clang (pointers.c is the C side)."""
import ctypes.util
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

FIXTURES = Path(__file__).resolve().parent / 'fixtures/optional_pointer'
EXPECTED = (FIXTURES / 'pointers.out').read_text()
ARM64_IMAGE = 'localhost/sloppy-arm64:latest'


def build(compiler, source, binary, *flags):
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr


@pytest.mark.parametrize('mode', ['default', 'release', 'debug'])
def test_optional_pointer_x86_64(compiler, tmp_path, mode):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or shutil.which('cc') is None:
        pytest.skip('the native check needs x86-64 Linux and a C compiler')
    library = tmp_path / 'libpointers.so'
    built = subprocess.run(['cc', '-std=c11', '-O2', '-shared', '-fPIC', FIXTURES / 'pointers.c', '-o', library],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    source = tmp_path / 'pointers.dewy'
    source.write_text((FIXTURES / 'pointers.dewy.in').read_text().replace('LIBRARY', f"'{library}'"))
    binary = tmp_path / 'pointers'
    build(compiler, source, binary, *([] if mode == 'default' else [f'--{mode}']))
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert (ran.returncode, ran.stdout) == (0, EXPECTED), ran.stderr


def test_optional_pointer_arm64(compiler, tmp_path):
    clang = shutil.which('clang')
    podman = shutil.which('podman')
    if platform.system() != 'Linux' or clang is None or shutil.which('ld.lld') is None or podman is None:
        pytest.skip('the aarch64 check needs clang, ld.lld and podman')
    if subprocess.run([podman, 'image', 'exists', ARM64_IMAGE], capture_output=True, timeout=30).returncode != 0:
        pytest.skip(f'the aarch64 check runs in {ARM64_IMAGE}')
    work = tmp_path / 'arm64'
    work.mkdir()
    built = subprocess.run([clang, '--target=aarch64-linux-gnu', '-O2', '-fPIC', '-shared', '-nostdlib', '-ffreestanding',
                            '-fuse-ld=lld', FIXTURES / 'pointers.c', '-o', work / 'libpointers.so'],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    source = work / 'pointers.dewy'
    source.write_text((FIXTURES / 'pointers.dewy.in').read_text().replace('LIBRARY', "'/w/libpointers.so'"))
    build(compiler, source, work / 'default', '--target', 'aarch64-linux')
    build(compiler, source, work / 'release', '--target', 'aarch64-linux', '--release')
    ran = subprocess.run([podman, 'run', '--rm', '-v', f'{work}:/w:Z', ARM64_IMAGE, 'sh', '-c', '/w/default && /w/release'],
                         capture_output=True, text=True, timeout=300)
    assert (ran.returncode, ran.stdout) == (0, EXPECTED * 2), ran.stderr


SQLITE = ctypes.util.find_library('sqlite3')

SQLITE_PROGRAM = """# sqlite3_open fills a `sqlite3 **` out-parameter: a `ptr<ptr<uint8>?>` slot in an array.
$extern(lib='%s')
sqlite3_open = (name:string db:ptr<ptr<uint8>?>):>int32
$extern(lib='%s')
sqlite3_close = (db:ptr<uint8>):>int32
main = ():>void => $unsafe {
    let slot:array<ptr<uint8>?> = [none]
    printl(slot[0] is? none)
    let status = sqlite3_open(":memory:" slot.ptr)
    printl(status slot[0] isnt? none)
    let db = slot[0]
    if db isnt? none { printl(sqlite3_close(db)) }
}
"""


@pytest.mark.parametrize('mode', ['default', 'release'])
def test_optional_pointer_sqlite_out_parameter(compiler, tmp_path, mode):
    if SQLITE is None or platform.system() != 'Linux':
        pytest.skip('the out-parameter check against sqlite3 needs libsqlite3 on Linux')
    source = tmp_path / 'sqlite.dewy'
    source.write_text(SQLITE_PROGRAM % (SQLITE, SQLITE))
    binary = tmp_path / 'sqlite'
    build(compiler, source, binary, *([] if mode == 'default' else [f'--{mode}']))
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert (ran.returncode, ran.stdout) == (0, 'true\n0 true\n0\n'), ran.stderr
