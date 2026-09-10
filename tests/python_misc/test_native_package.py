"""Release packaging requires consistent generations, binaries and sources."""
import hashlib
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def pair_fixture(path):
    path.mkdir()
    names = ['dewy-stage0', 'dewy-stage1', 'dewy-stage2', 'dewy',
             'udewy-stage0', 'udewy-stage1', 'udewy-stage2', 'udewy']
    for name in names:
        (path / name).write_text('#!/bin/sh\nexit 0\n')
        (path / name).chmod(0o755)
    (path / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256((path / name).read_bytes()).hexdigest()}  {name}\n'
        for name in names))
    (path / 'SOURCE_SHA256SUMS').write_text(
        f'{hashlib.sha256((ROOT / "VERSION").read_bytes()).hexdigest()}  VERSION\n')


def test_package_matching_pair_and_library(tmp_path):
    pair = tmp_path / 'pair'
    pair_fixture(pair)
    archive = tmp_path / 'native.tar.gz'
    result = subprocess.run([ROOT / 'tools/package_native.sh', pair, archive],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    with tarfile.open(archive) as packed:
        names = set(packed.getnames())
        assert {'./dewy', './udewy', './VERSION', './SHA256SUMS',
                './library/unicode/grapheme_break.bin',
                './library/linux/system.dewy', './tools/dewy_gdb.py'} <= names
        assert './dewy/__main__.py' not in names
        assert packed.getmember('./dewy').mode & 0o111
        packed.extractall(tmp_path / 'unpacked', filter='data')
    checked = subprocess.run(['sha256sum', '--check', '--status', 'SHA256SUMS'],
                             cwd=tmp_path / 'unpacked', capture_output=True, check=False)
    assert checked.returncode == 0, checked.stderr


def test_package_rejects_changed_generation_or_source(tmp_path):
    pair = tmp_path / 'pair'
    pair_fixture(pair)
    archive = tmp_path / 'native.tar.gz'
    (pair / 'dewy-stage2').write_text('changed')
    result = subprocess.run([ROOT / 'tools/package_native.sh', pair, archive],
                            capture_output=True, check=False)
    assert result.returncode != 0
    assert not archive.exists()
    (pair / 'SOURCE_SHA256SUMS').write_text('0' * 64 + '  VERSION\n')
    result = subprocess.run([ROOT / 'tools/package_native.sh', pair, archive],
                            capture_output=True, check=False)
    assert result.returncode != 0
    assert not archive.exists()
