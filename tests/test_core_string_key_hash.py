"""Dictionaries' keyed string hash: short keys (sixteen bytes or fewer) take their own path,
which must give the same value as the sixteen-bytes-at-a-time loop for every length class.
(Dictionaries keyed by strings of each length class: tests/cases/dictionary/string_key_lengths.)"""
import struct
import subprocess

from tests.support import compiler  # noqa: F401  (fixture)

MASK = (1 << 64) - 1
KEY = 0x0123456789ABCDEF
TEXT = b'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def _mum(a, b):
    p = a * b
    return (p & MASK) ^ (p >> 64)


def _keyed_bytes(key, p):
    """The keyed string hash as lib/core/map.jo documents it, one loop for every length."""
    n = len(p)
    k1 = key ^ 0xE7037ED1A0B428DB
    h = key ^ ((n * 0x9E3779B97F4A7C15) & MASK)
    i = 0
    while n - i > 16:
        h = _mum(struct.unpack_from('<Q', p, i)[0] ^ k1, struct.unpack_from('<Q', p, i + 8)[0] ^ h)
        i += 16
    a = b = 0
    if n > 8:
        a = struct.unpack_from('<Q', p, max(n - 16, 0))[0]
        b = struct.unpack_from('<Q', p, n - 8)[0]
    elif n >= 4:
        a = struct.unpack_from('<I', p, 0)[0] | (struct.unpack_from('<I', p, n - 4)[0] << 32)
    elif n > 0:
        a = p[0] | (p[n >> 1] << 8) | (p[n - 1] << 16)
    h = _mum(a ^ k1, b ^ h)
    return _mum(h ^ key, n ^ k1)


VALUES = f'''
main = ():
    __hash_key_pin({KEY:#x})
    text = "{TEXT.decode()}"
    loop n in [0..{len(TEXT)}):
        print("{{__str_khash(text[0..n))}}")
'''


def _build_run(compiler, tmp_path, name, source):
    path = tmp_path / name
    path.write_text(source)
    binary = tmp_path / path.stem
    built = subprocess.run([compiler, 'build', path, '-o', binary], capture_output=True, text=True,
                           timeout=120, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    return subprocess.run([binary], capture_output=True, text=True, timeout=30, check=True).stdout


def test_short_and_long_string_hashes_match_the_documented_hash(compiler, tmp_path):
    got = _build_run(compiler, tmp_path, 'values.jo', VALUES).split()
    key = KEY | 1  # (a pinned key is odd)
    assert got == [str(_keyed_bytes(key, TEXT[:n])) for n in range(len(TEXT))]
