"""New byte scan-loop lowering matches source-order Python loops in all modes."""

import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler, target_name  # noqa: F401


LENGTHS = (*range(18), 31, 32, 33, 4095, 4096, 4097)
SOURCE = '''
@noinline
scan = (a: u8[], start: int, n: int, c: u8) -> int:
    i = start
    loop i < n and a[i] != c: i += 1
    i
@noinline
skip = (a: u8[], start: int, n: int, c: u8) -> int:
    i = start
    loop i < n and a[i] == c: i += 1
    i
@noinline
tally = (a: u8[], n: int, c: u8) -> int:
    i = 0
    count = 0
    loop i < n:
        if a[i] == c: count += 1
        i += 1
    count
@noinline
class_scan = (a: u8[], n: int) -> int:
    i = 0
    loop i < n and a[i] >= u8(128): i += 1
    i
main = ():
    a: u8[]
    loop i in [0..4097): a.push(u8((i * 37 + i / 7) % 256))
    loop n in [0..18):
        print("class:{n}:{class_scan(a, n)}")
        loop c in [0, 1, 128, 255]:
            print("tally:{n}:{c}:{tally(a, n, u8(c))}")
            loop start in [0, 1, n - 1, n]:
                if start < 0: continue
                print("scan:{n}:{c}:{start}:{scan(a, start, n, u8(c))}")
                print("skip:{n}:{c}:{start}:{skip(a, start, n, u8(c))}")
    loop n in [31, 32, 33, 4095, 4096, 4097]:
        print("class:{n}:{class_scan(a, n)}")
        loop c in [0, 1, 128, 255]:
            print("tally:{n}:{c}:{tally(a, n, u8(c))}")
            loop start in [0, 1, n - 1, n]:
                print("scan:{n}:{c}:{start}:{scan(a, start, n, u8(c))}")
                print("skip:{n}:{c}:{start}:{skip(a, start, n, u8(c))}")
'''


def expected():
    data = bytes((i * 37 + i // 7) % 256 for i in range(4097))
    want = {}
    for n in LENGTHS:
        want[f'class:{n}'] = str(next((i for i in range(n) if data[i] < 128), n))
        for c in (0, 1, 128, 255):
            want[f'tally:{n}:{c}'] = str(data[:n].count(c))
            for start in (0, 1, n - 1, n):
                if start < 0:
                    continue
                want[f'scan:{n}:{c}:{start}'] = str(next((i for i in range(start, n)
                                                          if data[i] == c), max(start, n)))
                want[f'skip:{n}:{c}:{start}'] = str(next((i for i in range(start, n)
                                                          if data[i] != c), max(start, n)))
    return want


@pytest.fixture(scope='module')
def binaries(compiler, tmp_path_factory):
    directory = tmp_path_factory.mktemp('diff_scanloops')
    source = directory / 'scan.jo'
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


def test_differential_scanloops(binaries):
    want = expected()
    assert len(binaries) == 5, f'Missing target: {binaries.keys()}'
    for mode, binary in binaries.items():
        command = ([shutil.which('node'), binary] if mode == 'wasm' else
                   [shutil.which('qemu-aarch64'), binary] if mode == 'arm64' else [binary])
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f'{mode}: {result.stdout}{result.stderr}'
        got = dict(line.rsplit(':', 1) for line in result.stdout.splitlines())
        assert got == want, (mode, [(key, got.get(key), value) for key, value in want.items()
                                   if got.get(key) != value][:10])
