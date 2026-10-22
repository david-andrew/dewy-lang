"""compiler/base64.dewy, the base64 of the web page's module and icon and of a macOS
bundle's signature hashes: it ships, and its frozen implementation-language twin
compiler/base64.jo writes the same text."""
import base64
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
    """Every length to a few blocks (each padding), all byte values, and a large file."""
    rng = random.Random(7)
    out = [bytes(rng.randrange(256) for _ in range(n)) for n in range(14)]
    out.append(bytes(range(256)))
    out.append(b'\xff' * 7 + b'\x00' * 5)
    out.append(rng.randbytes(300_001))
    return out


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_base64_matches_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'base64_dewy.dewy', tmp_path / 'base64-dewy', release)
    jo = build(compiler, FIXTURES / 'base64_jo.jo', tmp_path / 'base64-jo', release)
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
    assert outputs[0].decode().split('\n')[:-1] == [base64.b64encode(blob).decode() for blob in data]


@pytest.mark.core_quick
def test_selfhost_base64_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/base64.dewy\0' in binary
    assert b'/compiler/base64.jo\0' not in binary
