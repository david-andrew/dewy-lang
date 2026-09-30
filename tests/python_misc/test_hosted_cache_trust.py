"""Hosted pickle caches load only from this user's private store (September 29
audit follow-up, item 2): unpickling runs code, and a digest in a file name
establishes freshness, not who produced the file."""
import os
import pickle
import subprocess
import sys
from pathlib import Path

from dewy.cache_location import private_cache_dir, trusted_cache_file

ROOT = Path(__file__).resolve().parents[2]


class Marker:
    """Unpickling it writes `path`: evidence that a pickle was loaded."""
    def __init__(self, path: Path):
        self.path = path

    def __reduce__(self):
        return (Path.write_text, (self.path, 'loaded'))


def test_project_pickles_are_never_loaded(tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>int64=>42\n')
    marker = tmp_path / 'marker'
    # Plant a pickle exactly where the hosted parser once looked for this
    # module's cache entry, relative to the project directory.
    import hashlib
    from dewy.semantic.check import _PARSER_SOURCE_DIGEST
    digest = hashlib.sha256(_PARSER_SOURCE_DIGEST + source.read_text().encode()).hexdigest()[:24]
    planted = tmp_path / '__dewycache__' / 'parse'
    planted.mkdir(parents=True)
    (planted / f'main-{digest}.pickle').write_bytes(pickle.dumps(Marker(marker)))
    env = os.environ | {'PYTHONPATH': str(ROOT), 'DEWY_LIBRARY_ROOT': str(ROOT / 'library'),
                        'DEWY_HOSTED_CACHE_DIR': str(tmp_path / 'private')}
    result = subprocess.run([sys.executable, '-m', 'dewy', str(source)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=600)
    assert result.returncode == 42, result.stdout + result.stderr
    assert not marker.exists()
    assert any((tmp_path / 'private').rglob('*.pickle'))


def test_shared_directories_are_not_trusted(tmp_path, monkeypatch):
    shared = tmp_path / 'shared'
    shared.mkdir()
    monkeypatch.setenv('DEWY_HOSTED_CACHE_DIR', str(shared))
    directory = private_cache_dir('parse')
    assert directory is not None and trusted_cache_file(directory / 'absent') is False
    entry = directory / 'entry.pickle'
    entry.write_bytes(b'')
    assert trusted_cache_file(entry)
    directory.chmod(0o777)
    assert private_cache_dir('parse') is None and not trusted_cache_file(entry)
    directory.chmod(0o700)
    entry.chmod(0o666)
    assert not trusted_cache_file(entry)
