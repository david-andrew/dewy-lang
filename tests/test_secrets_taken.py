"""Secrets (docs/LANGUAGE.md "Secrets", provisional, D10): `=?` with a secret operand takes time
that depends only on the lengths. Timing is noisy, so instructions are counted instead: a
comparison that differs at the first byte runs as many instructions as one that differs at the
last. Plain strings and byte arrays keep their early exit (the control)."""
import subprocess

import pytest

from tests.support import compiler
from tools.compiler import speed
from tools.filelock import lock_exclusive

COMPARE = r'''
main = (args:array<string>) => {
    let kind = args[1]
    let at = args[2]
    let n = 4096
    let chars:array<string> = []
    loop i in [0..n) chars.push("a")
    let a = chars.join("")
    if at =? "first" {chars[0] = "b"} else {chars[n - 1] = "b"}
    let others = [chars.join("") chars.join("")]
    let raw:array<uint8> = []
    loop i in [0..n) raw.push(7)
    let other:array<uint8> = raw.copy
    if at =? "first" {other[0] = 8} else {other[n - 1] = 8}
    let others_raw = [other other.copy]
    let hits = 0
    if kind =? "secret" {
        let s:secret<string> = a
        let k = secret(raw)
        loop i in [0..2000) {
            if s =? others[i % 2] {hits += 1}
            if k not=? others_raw[i % 2] {hits += 1}
        }
    } else {
        loop i in [0..2000) {
            if a =? others[i % 2] {hits += 1}
            if raw not=? others_raw[i % 2] {hits += 1}
        }
    }
    printl(hits)
}
$runtime_checks
'''


def _counter():
    try:
        speed.CACHE.mkdir(parents=True, exist_ok=True)
        with (speed.CACHE / 'speed.lock').open('w') as lock:
            lock_exclusive(lock)
            return speed.Counter('auto')
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        pytest.skip(f'no instruction counters: {error}')


def test_secret_equality_runs_the_same_instructions_wherever_the_bytes_differ(compiler, tmp_path):
    source = tmp_path / 'compare.dewy'
    source.write_text(COMPARE)
    binary = tmp_path / 'compare'
    built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                           capture_output=True, text=True, timeout=180, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    counter = _counter()
    counts = {}
    for kind in ('secret', 'plain'):
        for at in ('first', 'last'):
            instructions, out = counter.run([str(binary), kind, at], speed.clean_env())
            assert out.strip() == '2000', (kind, at, out)
            counts[kind, at] = instructions
    plain = counts['plain', 'last'] - counts['plain', 'first']
    secret = abs(counts['secret', 'last'] - counts['secret', 'first'])
    # 4000 comparisons of 4 KiB: an early exit saves millions of instructions. The secret runs
    # differ only in setting up the inputs (tens of instructions); one word per comparison of
    # leaked work would show as thousands.
    assert plain > 1_000_000, counts
    assert secret < 1_000, counts
