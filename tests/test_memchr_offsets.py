"""Empty byte spans must not wrap their offsets into a wide load."""
import shutil
import subprocess

import pytest

from tests.support import compiler
from tests.test_byte_find import build_run


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [(), ('--release',), ('-g',), ('--target', 'wasm32'), ('--target', 'aarch64-linux')])
def test_memchr_extreme_empty_offsets(compiler, tmp_path, flags):
    run_memchr(compiler, tmp_path, '''
@noinline
probe = (start: int, stop: int) -> int:
    __memchr(null, start, stop, u8(33))
main = () -> int:
    hi = 9223372036854775807
    lo = -9223372036854775807 - 1
    loop start in [hi, hi - 1, hi - 7, hi - 8, 0, -1, lo + 1, lo]:
        if probe(start, start) != -1: return 1
        if probe(start, lo) != -1: return 2
        if start >= 0 and probe(start, 0) != -1: return 3
        if start >= 3 and find_byte("abc", u8(33), start) != -1: return 4
    # A real short span whose logical indices approach INT64_MAX. The raw
    # pointer is rebased so only its final three bytes are in the span.
    a = fill(u8(7), 32)
    p = data(a) - (hi - 3)
    a[2] = 33
    if __memchr(p, hi - 3, hi, u8(33)) != hi - 1: return 5
    a[2] = 7
    a[3] = 33
    if __memchr(p, hi - 3, hi, u8(33)) != -1: return 6
    42
''', flags)


def run_memchr(compiler, tmp_path, source, flags):
    if 'aarch64-linux' not in flags:
        return build_run(compiler, tmp_path, source, flags)
    qemu = shutil.which('qemu-aarch64') or shutil.which('qemu-aarch64-static')
    if not qemu:
        pytest.skip('QEMU is needed to execute the ARM portable body')
    path = tmp_path / 'offsets.jo'
    path.write_text(source)
    binary = tmp_path / 'offsets'
    built = subprocess.run([compiler, 'build', path, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([qemu, binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 42, ran.stdout + ran.stderr
