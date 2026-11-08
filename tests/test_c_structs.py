"""C structs by value in `$extern` signatures against independently compiled C.

The same program runs natively on x86-64 (System V) and, built for aarch64-linux,
in the sloppy-arm64 container (AAPCS64) against the library cross-built with
clang. Expected output agrees with a C driver making the same calls."""
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

FIXTURES = Path(__file__).resolve().parent / 'fixtures/c_structs'
EXPECTED = (FIXTURES / 'structs.out').read_text()
ARM64_IMAGE = 'localhost/sloppy-arm64:latest'


def build(compiler, source, binary, *flags):
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr


@pytest.mark.parametrize('mode', ['default', 'release', 'debug'])
def test_c_structs_x86_64(compiler, tmp_path, mode):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or shutil.which('cc') is None:
        pytest.skip('the System V check needs x86-64 Linux and a C compiler')
    library = tmp_path / 'libstructs.so'
    built = subprocess.run(['cc', '-std=c11', '-O2', '-shared', '-fPIC', FIXTURES / 'structs.c', '-o', library],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    source = tmp_path / 'structs.dewy'
    source.write_text((FIXTURES / 'structs.dewy.in').read_text().replace('LIBRARY', f"'{library}'"))
    binary = tmp_path / 'structs'
    build(compiler, source, binary, *([] if mode == 'default' else [f'--{mode}']))
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert (ran.returncode, ran.stdout) == (0, EXPECTED), ran.stderr


def test_c_structs_arm64(compiler, tmp_path):
    clang = shutil.which('clang')
    podman = shutil.which('podman')
    if platform.system() != 'Linux' or clang is None or shutil.which('ld.lld') is None or podman is None:
        pytest.skip('the AAPCS64 check needs clang, ld.lld and podman')
    if subprocess.run([podman, 'image', 'exists', ARM64_IMAGE], capture_output=True, timeout=30).returncode != 0:
        pytest.skip(f'the AAPCS64 check runs in {ARM64_IMAGE}')
    work = tmp_path / 'arm64'
    work.mkdir()
    built = subprocess.run([clang, '--target=aarch64-linux-gnu', '-O2', '-fPIC', '-shared', '-nostdlib', '-ffreestanding',
                            '-fuse-ld=lld', FIXTURES / 'structs.c', '-o', work / 'libstructs.so'],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    source = work / 'structs.dewy'
    source.write_text((FIXTURES / 'structs.dewy.in').read_text().replace('LIBRARY', "'/w/libstructs.so'"))
    build(compiler, source, work / 'default', '--target', 'aarch64-linux')
    build(compiler, source, work / 'release', '--target', 'aarch64-linux', '--release')
    ran = subprocess.run([podman, 'run', '--rm', '-v', f'{work}:/w:Z', ARM64_IMAGE, 'sh', '-c', '/w/default && /w/release'],
                         capture_output=True, text=True, timeout=300)
    assert (ran.returncode, ran.stdout) == (0, EXPECTED * 2), ran.stderr


def test_c_structs_refused_on_windows(compiler, tmp_path):
    source = tmp_path / 'pair.dewy'
    source.write_text("Pair:type = [a:int32 b:int32]\ntotal = (p:Pair):>int32 => $extern(lib='kernel32')\n"
                      "main = ():>void => $unsafe printl(total(Pair[1 2]))\n")
    built = subprocess.run([compiler, 'build', source, '--target', 'x86_64-windows', '-o', tmp_path / 'pair.exe'],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode != 0
    assert 'C structs cannot cross by value on Windows yet: pass a `ptr<Pair>` to it' in built.stdout + built.stderr
