"""Secrets (docs/LANGUAGE.md "Secrets", provisional, D10): `=?` with a secret operand takes time
that depends only on the lengths. Timing is noisy, so instructions are counted instead: a
comparison that differs at the first byte runs as many instructions as one that differs at the
last. Plain strings and byte arrays keep their early exit (the control). Writing a secret makes a
file only its owner can read, 0o600 from its creation (lib/std/files.jo's __fsys_write)."""
import os
import stat
import subprocess
import sys

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


WRITE = r'''
main = (args:array<string>) => {
    let dir = args[1]
    let pass:secret<string> = "hunter2"
    let raw:array<uint8> = [1 2 3]
    printl(p"{dir}/new.txt".write_text(pass) ?? -1)
    printl(write_text("{dir}/text.txt" pass) ?? -1)
    printl(p"{dir}/key.bin".write_bytes(secret(raw)) ?? -1)
    printl(write_bytes("{dir}/raw.bin" secret(raw)) ?? -1)
    printl(p"{dir}/plain.txt".write_text("open") ?? -1)
    printl(p"{dir}/wide.txt".write_text(pass) ?? -1)
    printl(p"{dir}/owner.txt".write_text(pass) ?? -1)
    printl(p"{dir}/new.txt".read_text ?? "")
}
$runtime_checks
'''


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX permissions')
def test_writing_a_secret_makes_a_file_only_its_owner_can_read(compiler, tmp_path):
    source = tmp_path / 'write.dewy'
    source.write_text(WRITE)
    binary = tmp_path / 'write'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=180, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    out = tmp_path / 'out'
    out.mkdir()
    # (files a secret replaces keep only their owner's permissions)
    (out / 'wide.txt').write_text('old')
    (out / 'wide.txt').chmod(0o666)
    (out / 'owner.txt').write_text('old')
    (out / 'owner.txt').chmod(0o700)
    ran = subprocess.run([binary, out], capture_output=True, text=True, timeout=60, check=False,
                         preexec_fn=lambda: os.umask(0o022))
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.split() == ['7', '7', '3', '3', '4', '7', '7', 'hunter2']
    modes = {f.name: stat.S_IMODE(f.stat().st_mode) for f in out.iterdir()}
    assert modes == {'new.txt': 0o600, 'text.txt': 0o600, 'key.bin': 0o600, 'raw.bin': 0o600,
                     'plain.txt': 0o644, 'wide.txt': 0o600, 'owner.txt': 0o700}, {k: oct(v) for k, v in modes.items()}
