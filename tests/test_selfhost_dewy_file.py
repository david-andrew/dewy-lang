"""The Dewy file driver and frozen twin preserve declarations and first errors."""
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tools.compiler import parser_diff


def build_pair(seed, work, release):
    tree = work / 'source'
    shutil.copytree(parser_diff.ROOT / 'compiler', tree / 'compiler')
    shutil.copytree(parser_diff.ROOT / 'lib', tree / 'lib')
    main = tree / 'compiler/main.jo'
    main.write_text(main.read_text().replace('build:\n    opt = release\n', ''))
    binaries = []
    for side in ('dewy', 'twin'):
        if side == 'twin':
            for path in (tree / 'compiler').glob('*.jo'):
                path.write_text(path.read_text().replace("use 'dewy_file.dewy'", "use 'dewy_file.jo'"))
        binary = work / side
        run = subprocess.run([seed, 'build', main, '-o', binary,
                              *(['--release'] if release else [])],
                             env=parser_diff.environment(tree / 'lib'),
                             capture_output=True, timeout=300)
        assert run.returncode == 0, run.stdout + run.stderr
        binaries.append(binary)
    return tuple(binaries)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_file_driver_matches_frozen(compiler, tmp_path, release):
    pair = build_pair(compiler, tmp_path, release)
    cases = parser_diff.ROOT / 'tests/cases'
    directories = ('target', 'testing', 'misc', 'witness', 'directives', 'ffi',
                   'overload', 'constant', 'frontend', 'truncated')
    assert all((cases / directory).is_dir() for directory in directories)
    sources = sorted(p for directory in directories
                     for p in (cases / directory).glob('*.dewy'))
    sources += parser_diff.generated(tmp_path / 'generated', 4)
    failures = parser_diff.compare(pair, sources, tmp_path, release, workers=1)
    assert not failures, '\n'.join(f'{path}: {reason}' for path, reason in failures)
    shared = tmp_path / 'shared-panics'
    assert not shared.exists(), shared.read_text()


@pytest.mark.core_quick
def test_file_driver_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_file.dewy\0' in binary
    assert b'/compiler/dewy_file.jo\0' not in binary
