"""compiler/sha.dewy, the SHA-256 and SHA-1 of a macOS program's code signature, LC_UUID and
sealed icon: it ships, and its frozen implementation-language twin compiler/sha.jo gives the
same digests, both hashlib's."""
import hashlib
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
    """Every length to a few blocks (each padding case: 55, 56, 63, 64 and 119 bytes), all byte
    values, a page and a byte more, and a large file."""
    rng = random.Random(13)
    out = [rng.randbytes(n) for n in range(140)]
    out += [bytes(range(256)), b'\xff' * 64, b'\x00' * 4096, rng.randbytes(4097), rng.randbytes(300_001)]
    return out


def digests(blob):
    n = len(blob)
    show = lambda digest: ''.join(f'{b} ' for b in digest)
    return (show(hashlib.sha256(blob).digest()) + '| ' + show(hashlib.sha256(blob[n // 3:n // 3 + n // 2]).digest())
            + '| ' + show(hashlib.sha1(blob).digest()))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_sha_matches_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'sha_dewy.dewy', tmp_path / 'sha-dewy', release)
    jo = build(compiler, FIXTURES / 'sha_jo.jo', tmp_path / 'sha-jo', release)
    data = inputs()
    paths = []
    for k, blob in enumerate(data):
        path = tmp_path / f'in{k}.bin'
        path.write_bytes(blob)
        paths.append(path)
    outputs = []
    for binary in (dewy, jo):
        ran = subprocess.run([binary, *paths], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].decode().split('\n')[:-1] == [digests(blob) for blob in data]


@pytest.mark.core_quick
def test_selfhost_sha_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/sha.dewy\0' in binary
    assert b'/compiler/sha.jo\0' not in binary
