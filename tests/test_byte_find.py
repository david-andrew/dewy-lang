"""Bounded dynamic-byte searches: exact bytes, tails, inaccessible pages and live values."""
import os
import platform
import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler


def build_run(compiler, tmp_path, source, flags=(), no_avx=False):
    if 'wasm32' in flags and shutil.which('node') is None:
        pytest.skip('Node is needed for web execution')
    path = tmp_path / 'search.jo'
    path.write_text(source)
    binary = tmp_path / 'search'
    env = dict(os.environ)
    env.pop('DEWY_NO_AVX', None)
    if no_avx:
        env['DEWY_NO_AVX'] = '1'
    built = subprocess.run([compiler, 'build', path, '-o', binary, '--ir', *flags],
                           env=env, capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if 'wasm32' in flags:
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = ['node', runner]
    ran = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
    assert ran.returncode == 42, ran.stdout + ran.stderr
    return built.stdout


@pytest.mark.core_quick
@pytest.mark.parametrize('flags', [(), ('--release',), ('-g',), ('--target', 'wasm32')])
def test_byte_find_all_bytes_and_starts(compiler, tmp_path, flags):
    ir = build_run(compiler, tmp_path, '''
@noinline
oracle = (p: *u8, start: int, n: int, c: u8) -> int:
    loop i in [start..n):
        if p[i] == c: return i
    -1
main = () -> int:
    bytes: u8[]
    loop i in [0..513): bytes.push(u8((i * 37 + i / 7) % 256))
    p = data(bytes)
    loop n in [0, 1, 2, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 255, 256, 257, 513]:
        loop c in [0..256):
            loop start in [0, 1, 7, 15, n - 1, n, n + 1, n + 100]:
                if start < 0: continue
                if __memchr(p, start, n, u8(c)) != oracle(p, start, n, u8(c)): return 1
    s = str_from_bytes(bytes)
    if find_byte(s, u8(0), -10) != 0: return 2
    if find_byte("", u8(0)) != -1: return 3
    if find("abc", "b", -1) != -1: return 4
    # Embedded NUL and malformed UTF-8 remain bytes, and starts stay byte offsets.
    text = "a\\x80\\x00\\xffz\\x80"
    if find(text, "\\x80") != 1 or find(text, "\\x80", 2) != 5: return 5
    if count(text, "\\x80") != 2: return 6
    parts = split(text, "\\x80")
    if parts.len() != 3 or parts[0] != "a" or parts[1] != "\\x00\\xffz" or parts[2] != "": return 7
    if __memchr(null, 0, 0, u8(0)) != -1: return 8
    if __memchr(null, 1, 0, u8(0)) != -1: return 9
    42
''', flags)
    native_x64 = platform.machine().lower() in ('x86_64', 'amd64') and flags in ((), ('--release',))
    if native_x64:
        assert 'findbyte' in ir
    else:
        assert 'findbyte' not in ir


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('no_avx', [False, True], ids=['avx2-host', 'sse2'])
def test_byte_find_guard_pages(compiler, tmp_path, release, no_avx):
    if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('guard-page syscalls require x86-64 Linux')
    build_run(compiler, tmp_path, '''main = () -> int:
    area = syscall(9, 0, 12288, 3, 0x22, -1, 0)
    if area < 0: return 1
    if syscall(10, area, 4096, 0) != 0: return 2
    if syscall(10, area + 8192, 4096, 0) != 0: return 3
    loop n in [0..258):
        loop at_end in [false, true]:
            p = (if at_end: area + 8192 - n else: area + 4096) as *u8
            loop c in [u8(0), u8(1), u8(127), u8(128), u8(255)]:
                loop i in [0..n): p[i] = c xor 1
                if __memchr(p, 0, n, c) != -1: return 4
                loop i in [0..n):
                    p[i] = c
                    if __memchr(p, 0, n, c) != i: return 5
                    if __memchr(p, i, n, c) != i: return 6
                    if __memchr(p, i + 1, n, c) != -1: return 7
                    p[i] = c xor 1
    if syscall(11, area, 12288) != 0: return 8
    42
''', ('--release',) if release else (), no_avx)


@pytest.mark.parametrize('release', [False, True])
def test_byte_find_live_results_and_mutation(compiler, tmp_path, release):
    # Keep more results live than integer registers; mutate the searched memory
    # between calls, so searches must not be treated as memory-independent CSE.
    statements = '\n'.join(f'        r{i} = __memchr(p, {i}, n, u8(7))' for i in range(24))
    combine = ' + '.join(f'r{i}' for i in range(24))
    source = ('probe = (p: *u8, n: int, rounds: int) -> int:\n    total = 0\n'
              '    loop _ in [0..rounds):\n' + statements + '\n        total += ' + combine + '\n    total\n' + '''
main = () -> int:
    a = fill(u8(8), 96)
    a[57] = 7
    if probe(data(a), 96, 2) != 2736: return 1
    a[57] = 8
    if probe(data(a), 96, 2) != -48: return 2
    a[13] = 7
    if probe(data(a), 96, 2) != 344: return 3
    42
''')
    build_run(compiler, tmp_path, source, ('--release',) if release else ())
