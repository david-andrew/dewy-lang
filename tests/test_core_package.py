"""The downloadable core must run after extraction, without build tools on PATH."""
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from tests.test_core import Scripts
from tools.compiler.package import package


@pytest.fixture(scope='module')
def toolchain():
    compiler = os.environ.get('DEWY_CORE_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_CORE_COMPILER for package checks')
    return Path(compiler).resolve(strict=True).parent.parent


def test_core_packaged_toolchain(toolchain, tmp_path):
    archive = package(toolchain, tmp_path / 'core.tar.gz', revision='test-revision')
    assert archive.with_name(archive.name + '.sha256').read_text() == (
        f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  core.tar.gz\n')
    unpacked = tmp_path / 'unpacked'
    with tarfile.open(archive) as contents:
        contents.extractall(unpacked, filter='data')
    moved = tmp_path / 'relocated toolchain'
    (unpacked / 'dewy-core').rename(moved)
    metadata = json.loads((moved / 'PACKAGE.json').read_text())
    assert metadata['revision'] == 'test-revision'
    for name, expected in metadata['files'].items():
        assert hashlib.sha256((moved / name).read_bytes()).hexdigest() == expected
    compiler = moved / 'bin' / ('dewy-core.exe' if os.name == 'nt' else 'dewy-core')
    assert os.access(compiler, os.X_OK)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['PATH'] = ''

    def run(*arguments):
        result = subprocess.run([compiler, *arguments], cwd=tmp_path, env=env,
                                capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    assert os.path.normcase(run('--print-lib').stdout.strip()) == os.path.normcase(str(moved / 'lib'))
    source = tmp_path / 'sample.dewy'
    source.write_text('main=()=>{let values=[20 22] return sum(values)}\n')
    binary = tmp_path / ('sample.exe' if os.name == 'nt' else 'sample')
    run('build', source, '-o', binary)
    executed = subprocess.run([binary], cwd=tmp_path, env=env, capture_output=True,
                              text=True, timeout=10, check=False)
    assert executed.returncode == 42, executed.stdout + executed.stderr
    run('build', source, '--target', 'wasm', '-o', tmp_path / 'sample-web')
    node = shutil.which('node')
    assert node, 'Node is required for the packaged web compiler check'
    scripts = Scripts()
    scripts.feed((tmp_path / 'sample-web.html').read_text())
    runner = tmp_path / 'sample.cjs'
    runner.write_text('\n'.join(scripts.parts))
    executed = subprocess.run([node, runner], cwd=tmp_path, env=env, capture_output=True,
                              text=True, timeout=10, check=False)
    assert executed.returncode == 42, executed.stdout + executed.stderr
    # Templates, game libraries and embedded assets must ship with the compiler.
    run('new', tmp_path / 'my-game')
    game = tmp_path / 'my-game/main.dewy'
    run('build', game, '-o', tmp_path / 'game-native')
    run('build', game, '--target', 'wasm', '-o', tmp_path / 'game-web')
    assert (tmp_path / 'game-web.html').is_file()


@pytest.mark.parametrize('changed', ['compiler', 'lib/core/rt.jo'])
def test_core_package_rejects_changed_payload(toolchain, tmp_path, changed):
    copy = tmp_path / 'toolchain'
    copy.mkdir()
    provenance = 'HOST_BUILD.json' if (toolchain / 'HOST_BUILD.json').is_file() else 'build.json'
    shutil.copy2(toolchain / provenance, copy / provenance)
    for name in ('bin', 'lib'):
        shutil.copytree(toolchain / name, copy / name)
    for name in ('LICENSE', 'NOTICE', 'UPSTREAM.json'):
        shutil.copy2(toolchain / name, copy / name)
    if changed == 'compiler':
        changed = 'bin/dewy-core.exe' if os.name == 'nt' else 'bin/dewy-core'
    with (copy / changed).open('ab') as stream:
        stream.write(b'changed')
    output = tmp_path / 'changed.tar.gz'
    with pytest.raises(ValueError, match='toolchain changed since its build'):
        package(copy, output)
    assert not output.exists()
