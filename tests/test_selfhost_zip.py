"""Self-hosting pilot: compiler/zip.jo translated to Dewy writes the same archives."""
import random
import subprocess
import zipfile
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


def inputs(directory):
    rng = random.Random(7)
    words = ['alpha', 'beta', 'gamma', 'zip', 'crc', 'deflate', 'header', 'données']
    files = {
        'empty.bin': b'',
        'one.txt': b'x',
        'notes.txt': ' '.join(rng.choice(words) for _ in range(20000)).encode(),
        'random.bin': rng.randbytes(70000),
        'données é.txt': 'Unicode name, Unicode text: é 🙂\n'.encode() * 50,
    }
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return files


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_zip_matches_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'zip.dewy', tmp_path / 'zip-dewy', release)
    jo = build(compiler, FIXTURES / 'zip_jo.jo', tmp_path / 'zip-jo', release)
    files = inputs(tmp_path)
    selections = [['one.txt'], ['empty.bin', 'notes.txt'], list(files)]
    for i, names in enumerate(selections):
        archives = []
        for binary in (dewy, jo):
            archive = f'{binary.name}-{i}.zip'
            ran = subprocess.run([binary, archive, *names], cwd=tmp_path,
                                 capture_output=True, text=True, timeout=60)
            assert ran.returncode == 0, ran.stdout + ran.stderr
            archives.append((tmp_path / archive).read_bytes())
        assert archives[0] == archives[1], names
        with zipfile.ZipFile(tmp_path / f'{dewy.name}-{i}.zip') as z:
            assert z.testzip() is None
            assert z.namelist() == names
            for name in names:
                assert z.read(name) == files[name]
            methods = {info.filename: info.compress_type for info in z.infolist()}
        if 'notes.txt' in names:
            assert methods['notes.txt'] == zipfile.ZIP_DEFLATED
            assert methods['empty.bin'] == zipfile.ZIP_STORED
