"""compiler/line_table.dewy, the line and column of the compiler's source positions: it
ships, and its frozen implementation-language twin compiler/line_table.jo gives the same
answers, both those of an independent oracle."""
import bisect
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

FIXTURES = Path(__file__).resolve().parent / 'fixtures/selfhost'


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def inputs():
    """Every length to a few words with newlines anywhere, newline runs, CRLF, text
    without a newline, multibyte characters and a large file."""
    rng = random.Random(11)
    alphabet = ['a', 'b', ' ', '\n', '\n', 'é', '→', '\r\n']
    out = [''.join(rng.choice(alphabet) for _ in range(n)) for n in range(40)]
    out += ['', '\n' * 17, 'x' * 33, '\n' + 'y' * 15 + '\n', 'z' * 16 + '\n']
    out.append(''.join(rng.choice(alphabet[:4] + ['abcdefgh' * 5]) for _ in range(60_000)))
    return out


def starts_of(text):
    return [0] + [i + 1 for i, b in enumerate(text.encode()) if b == 10]


def line_col(starts, off):
    k = bisect.bisect_right(starts, off) - 1
    return f'{k + 1} {off - starts[k] + 1}'


def oracle(texts):
    """The drivers' output, from Python's own newline search."""
    lines = []
    for f, text in enumerate(texts):
        starts = starts_of(text)
        lines.append(f'{f}:' + ''.join(f' {s}' for s in starts))
        n = len(text.encode())
        step = 1 if n <= 64 else 97
        forward = list(range(0, n + 1, step))
        back = list(range(forward[-1], -1, -step))
        lines += [f'{f} {o} {line_col(starts, o)}' for o in forward + back]
        middle = len(texts[0].encode()) // 2
        lines.append(f'0 . {line_col(starts_of(texts[0]), middle)}')
    return '\n'.join(lines) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_line_table_matches_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'line_table_dewy.dewy', tmp_path / 'lines-dewy', release)
    jo = build(compiler, FIXTURES / 'line_table_jo.jo', tmp_path / 'lines-jo', release)
    texts = inputs()
    paths = []
    for k, text in enumerate(texts):
        path = tmp_path / f'in{k}.txt'
        path.write_bytes(text.encode())
        paths.append(path)
    outputs = []
    for binary in (dewy, jo):
        ran = subprocess.run([binary, *paths], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].decode() == oracle(texts)


@pytest.mark.core_quick
def test_selfhost_line_table_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/line_table.dewy\0' in binary
    assert b'/compiler/line_table.jo\0' not in binary
