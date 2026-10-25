"""Bounded byte searches agree with Python across all executable targets."""

import shutil
import os
import platform
import subprocess

import pytest

from tests.support import Scripts, compiler, target_name  # noqa: F401


LENGTHS = (*range(18), 31, 32, 33, 4095, 4096, 4097)
SOURCE = '''
main = ():
    bytes: u8[]
    loop i in [0..4097): bytes.push(u8((i * 37 + i / 7) % 256))
    p = data(bytes)
    loop n in [0..18):
        loop c in [0, 1, 128, 255]:
            loop start in [0, 1, n - 1, n]:
                if start < 0: continue
                print("{n}:{c}:{start}:{__memchr(p, start, n, u8(c))}")
    loop n in [31, 32, 33, 4095, 4096, 4097]:
        loop c in [0, 1, 128, 255]:
            loop start in [0, 1, n - 1, n]:
                print("{n}:{c}:{start}:{__memchr(p, start, n, u8(c))}")
'''

PAGE_SOURCE = '''
main = ():
    base = syscall(9, 0, 16384, 3, 0x22, -1, 0)
    if base < 0: panic("mmap failed")
    if syscall(10, base, 4096, 0) != 0: panic("front guard failed")
    if syscall(10, base + 12288, 4096, 0) != 0: panic("back guard failed")
    loop n in [0, 1, 7, 8, 15, 16, 17, 31, 32, 33, 4095, 4096, 4097]:
        p = (base + 12288 - n) as *u8
        loop i in [0..n): p[i] = u8(8)
        if n > 0: p[n - 1] = u8(7)
        print("{n}:{__memchr(p, 0, n, u8(7))}:{__memchr(p, 0, n, u8(9))}")
    if syscall(11, base, 16384) != 0: panic("munmap failed")
'''


def expected():
    data = bytes((i * 37 + i // 7) % 256 for i in range(4097))
    return {
        f'{n}:{c}:{start}': str(data.find(bytes([c]), start, n))
        for n in LENGTHS for c in (0, 1, 128, 255)
        for start in (0, 1, n - 1, n) if start >= 0
    }


@pytest.fixture(scope='module')
def binaries(compiler, tmp_path_factory):
    directory = tmp_path_factory.mktemp('diff_byte_search')
    source = directory / 'search.jo'
    source.write_text(SOURCE)
    built = {}
    for name, flags in {'native': (), 'release': ('--release',), 'debug': ('-g',),
                        'wasm': ('--target', 'wasm32'),
                        'arm64': ('--target', target_name('linux-arm64'))}.items():
        if name == 'wasm' and not shutil.which('node'):
            continue
        if name == 'arm64' and not shutil.which('qemu-aarch64'):
            continue
        binary = directory / name
        result = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f'{name}: {result.stdout}{result.stderr}'
        if name == 'wasm':
            scripts = Scripts()
            scripts.feed(binary.with_suffix('.html').read_text())
            runner = directory / 'wasm.cjs'
            runner.write_text('\n'.join(scripts.parts))
            binary = runner
        built[name] = binary
    return built


def test_differential_byte_search(binaries):
    want = expected()
    assert len(want) >= 120
    assert len(binaries) == 5, f'Missing target: {binaries.keys()}'
    for mode, binary in binaries.items():
        command = ([shutil.which('node'), binary] if mode == 'wasm' else
                   [shutil.which('qemu-aarch64'), binary] if mode == 'arm64' else [binary])
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f'{mode}: {result.stdout}{result.stderr}'
        got = dict(line.rsplit(':', 1) for line in result.stdout.splitlines())
        assert got == want, (mode, [(key, got.get(key), value) for key, value in want.items()
                                   if got.get(key) != value][:10])


@pytest.mark.skipif(platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'),
                    reason='guard-page syscall harness requires x86-64 Linux')
def test_differential_byte_search_page_end(compiler, tmp_path):
    source = tmp_path / 'page.jo'
    source.write_text(PAGE_SOURCE)
    want = {str(n): (str(n - 1), '-1') for n in (0, 1, 7, 8, 15, 16, 17,
                                                31, 32, 33, 4095, 4096, 4097)}
    for mode, flags in {'native': (), 'release': ('--release',), 'debug': ('-g',)}.items():
        binary = tmp_path / mode
        built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, f'{mode}: {built.stdout}{built.stderr}'
        for sse in (False, True):
            env = dict(os.environ)
            if sse:
                env['DEWY_NO_AVX'] = '1'
            else:
                env.pop('DEWY_NO_AVX', None)
            ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=20)
            assert ran.returncode == 0, (mode, sse, ran.stdout, ran.stderr)
            got = {parts[0]: tuple(parts[1:]) for line in ran.stdout.splitlines()
                   if (parts := line.split(':'))}
            assert got == want, (mode, sse, got)
