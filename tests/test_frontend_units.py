"""Bounded delimiter searches and parse-unit scanning."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run_probe(compiler, tmp_path, text, release):
    source = tmp_path / 'units.jo'
    source.write_text(text)
    binary = tmp_path / 'units'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, timeout=90)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, timeout=30)
    assert ran.returncode == 42, ran.stdout + ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_delimiter_bounded_windows(compiler, tmp_path, release):
    run_probe(compiler, tmp_path, r'''
reference = (p: *u8, i: int, n: int, w: int) -> int:
    k = i
    loop k < n:
        c = p[k]
        if c == '\n':
            if w < 0 or k + w + 1 >= n: return k
            m = 1
            loop m <= w + 1 and (p[k + m] == ' ' or (w == 0 and p[k + m] <= ' ')): m += 1
            if m <= w + 1: return k
        else if w != -2 and (c == '"' or c == '#' or c == '\''): return k
        k += 1
    n
main = () -> int:
    bytes: u8[]
    loop i in [0..192): bytes.push(u8(65))
    p = data(bytes)
    loop seed in [0..64):
        loop j in [0..192):
            c = (j * 37 + seed * 13) % 29
            p[j] = if c < 12: u8(' ') else if c == 12: u8('\n') else if c == 13: u8('"') else if c == 14: u8('#') else if c == 15: u8('\'') else if c == 16: u8('\t') else: u8(128 + c)
        loop n in [0..96):
            loop i in [0..n + 1):
                assert(__find_newline(p, i, n) == reference(p, i, n, -2))
                assert(__find_delim(p, i, n) == reference(p, i, n, -1))
                assert(__find_line_delim(p, i, n) == reference(p, i, n, 0))
                assert(__find_line_delim4(p, i, n) == reference(p, i, n, 4))
                assert(__find_line_delim8(p, i, n) == reference(p, i, n, 8))
    loop ind in [0..13):
        loop at in [0..32):
            loop j in [0..192): p[j] = u8('x')
            p[at] = u8('\n')
            loop j in [1..ind + 1): p[at + j] = u8(' ')
            loop n in [at..at + 32):
                assert(__find_line_delim(p, 0, n) == reference(p, 0, n, 0))
                assert(__find_line_delim4(p, 0, n) == reference(p, 0, n, 4))
                assert(__find_line_delim8(p, 0, n) == reference(p, 0, n, 8))
    42
''', release)


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_parser_borrow_survives_interpolation(compiler, tmp_path, release):
    run_probe(compiler, tmp_path, r'''
combine = (a: int, b: int) -> int: a * 10 + b
main = () -> int:
    values = [1, 2, 3]
    f = (x: int) -> int: combine(x, values[1])
    text = "outer {"inner {f(4)}"} after {values[0..2).len()}"
    assert(text == "outer inner 42 after 2")
    assert((1 + 2 * 3 == 7 and not false) or false)
    assert(1 + 2 * 3 ^ 2 == 19)
    assert(f(4) == 42)
    42
''', release)
