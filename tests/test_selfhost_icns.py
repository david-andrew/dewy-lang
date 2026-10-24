"""compiler/icns.dewy, a macOS app bundle's icon: it ships, and its frozen
implementation-language twin compiler/icns.jo writes the same file, an independent
oracle's."""
import random
import struct
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


def png(width, rest):
    """A PNG's first 24 bytes (signature, IHDR's length, type, width and height), then rest."""
    return b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', width, width) + rest


def oracle(data):
    """Apple's .icns: 'icns' and the file's length, then one element: the PNG's type (by its
    width, from the IHDR chunk), the element's length and the PNG."""
    width = struct.unpack('>I', data[16:20])[0]
    kind = next((t for limit, t in ((16, b'icp4'), (32, b'icp5'), (64, b'icp6'), (128, b'ic07'), (256, b'ic08'))
                 if width <= limit), b'ic09')
    return b'icns' + struct.pack('>I', 16 + len(data)) + kind + struct.pack('>I', 8 + len(data)) + data


def inputs():
    """Each type's widths at and past its limit, a header alone, and a large body."""
    rng = random.Random(17)
    widths = [1, 16, 17, 32, 33, 64, 65, 128, 129, 256, 257, 1024, 2**31]
    out = [png(w, rng.randbytes(rng.randrange(200))) for w in widths]
    out += [png(48, b''), png(256, rng.randbytes(300_000))]
    return out


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_icns_matches_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'icns_dewy.dewy', tmp_path / 'icns-dewy', release)
    jo = build(compiler, FIXTURES / 'icns_jo.jo', tmp_path / 'icns-jo', release)
    data = inputs()
    for binary in (dewy, jo):
        paths = []
        for k, blob in enumerate(data):
            path = tmp_path / f'{binary.name}-{k}.png'
            path.write_bytes(blob)
            paths.append(path)
        ran = subprocess.run([binary, *paths], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        for path, blob in zip(paths, data):
            assert path.with_name(path.name + '.icns').read_bytes() == oracle(blob), path
