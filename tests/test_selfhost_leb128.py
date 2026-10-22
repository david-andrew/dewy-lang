"""compiler/leb128.dewy, the LEB128 encoders of the wasm, DWARF and Mach-O writers: it
ships, and its frozen implementation-language twin compiler/leb128.jo writes the same bytes."""
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


def values():
    """Every byte boundary from both sides, both signs, and random words."""
    rng = random.Random(5)
    out = {0, 2**63 - 1, -2**63}
    for bits in range(64):
        for v in (2**bits - 1, 2**bits, 2**bits + 1):
            out.update(x for x in (v, -v) if -2**63 <= x < 2**63)
    out.update(rng.randrange(-2**63, 2**63) >> rng.randrange(64) for _ in range(300))
    return sorted(out)


def uleb(v):
    if v < 0:
        return [v & 255]     # (a negative value writes its low byte alone)
    out = []
    while v >= 128:
        out.append(v & 127 | 128)
        v >>= 7
    return out + [v]


def sleb(v):
    out = []
    while True:
        byte = v & 127
        v >>= 7
        if (v == 0 and not byte & 64) or (v == -1 and byte & 64):
            return out + [byte]
        out.append(byte | 128)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_leb128_matches_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'leb128_dewy.dewy', tmp_path / 'leb128-dewy', release)
    jo = build(compiler, FIXTURES / 'leb128_jo.jo', tmp_path / 'leb128-jo', release)
    numbers = values()
    outputs = []
    for binary in (dewy, jo):
        ran = subprocess.run([binary, *map(str, numbers)], capture_output=True, text=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    expected = [' '.join(map(str, uleb(v))) + ' | ' + ' '.join(map(str, sleb(v))) for v in numbers]
    assert [line.rstrip() for line in outputs[0].splitlines()] == expected


@pytest.mark.core_quick
def test_selfhost_leb128_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/leb128.dewy\0' in binary
    assert b'/compiler/leb128.jo\0' not in binary
