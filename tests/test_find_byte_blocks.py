"""Repeated AVX2 search blocks preserve the first match and the readable span."""
import platform

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_byte_find import build_run


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('no_avx', [False, True], ids=['avx2-host', 'sse2'])
def test_repeated_blocks_at_guard_pages(compiler, tmp_path, release, no_avx):  # noqa: F811
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('guard-page syscalls require x86-64 Linux')
    build_run(compiler, tmp_path, '''main = () -> int:
    area = syscall(9, 0, 12288, 3, 0x22, -1, 0)
    if area < 0: return 1
    if syscall(10, area, 4096, 0) != 0: return 2
    if syscall(10, area + 8192, 4096, 0) != 0: return 3
    loop n in [383, 384, 385, 511, 512, 513, 1023, 1024, 1025, 4096]:
        loop at_end in [false, true]:
            p = (if at_end: area + 8192 - n else: area + 4096) as *u8
            loop c in [u8(0), u8(1), u8(127), u8(128), u8(255)]:
                loop i in [0..n): p[i] = c xor 1
                if __memchr(p, 0, n, c) != -1: return 4
                # Every lane, including the last vector of repeated blocks.
                loop i in [0..n):
                    p[i] = c
                    if __memchr(p, 0, n, c) != i: return 5
                    if __memchr(p, i, n, c) != i: return 6
                    if __memchr(p, i + 1, n, c) != -1: return 7
                    # Multiple matches must select the earliest vector/lane.
                    if i + 129 < n:
                        p[i + 129] = c
                        if __memchr(p, 0, n, c) != i: return 8
                        if __memchr(p, i + 1, n, c) != i + 129: return 9
                        p[i + 129] = c xor 1
                    # A matching byte outside a shorter span is not readable
                    # by that search, even when the physical page is mapped.
                    if __memchr(p, 0, i, c) != -1: return 10
                    p[i] = c xor 1
    if syscall(11, area, 12288) != 0: return 11
    42
''', ('--release',) if release else (), no_avx)
