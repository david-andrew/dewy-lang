"""Bootstrap a shallow checkout offline and reproduce the fixed point from the verified cache."""
import json
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.compiler import seed_archive as seed


@pytest.mark.nightly
def test_clean_shallow_offline_clone_reaches_fixed_point(tmp_path):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or not shutil.which('bwrap'):
        pytest.skip('requires a Linux x86-64 host with bubblewrap for private mount and network namespaces')
    checkout = tmp_path / 'checkout'
    subprocess.run(['git', 'clone', '-q', '--depth=1', '--no-tags', seed.ROOT.as_uri(), checkout], check=True)
    assert (checkout / '.git/shallow').is_file()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout) == subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=seed.ROOT)
    pin = json.loads((checkout / 'bootstrap-seed/pin.json').read_bytes())
    target = Path(pin['comparison_root'])
    work = tmp_path / 'build'
    (work / 'tmp').mkdir(parents=True)
    # Only the checkout, system toolchain and this empty build area are visible.
    sandbox = ['bwrap', '--unshare-net', '--die-with-parent', '--ro-bind', '/usr', '/usr',
               '--ro-bind', '/etc', '/etc', '--proc', '/proc', '--dev', '/dev']
    # Keep merged-/usr links intact. GCC locates cc1 relative to its
    # installed prefix, which changes if /bin/gcc appears to be a second installation.
    for path in (Path('/bin'), Path('/lib'), Path('/lib64')):
        if path.is_symlink():
            sandbox += ['--symlink', path.readlink(), path]
        elif path.exists():
            sandbox += ['--ro-bind', path, path]
    sandbox += ['--ro-bind', checkout, '/checkout', '--bind', work, str(target.parent),
                '--chdir', '/checkout', '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
                '--setenv', 'TMPDIR', str(target.parent / 'tmp'), '--setenv', 'LC_ALL', 'C']
    cmd = [*sandbox, 'python3', 'tools/compiler/build.py', '--bootstrap', '--fixed-point',
           '--output', target, '--seed-cache', target.parent / 'seed-cache']
    toolchain = work / target.name
    subprocess.run(cmd, check=True)
    built = json.loads((toolchain / 'build.json').read_bytes())
    assert built['live_generations_sha256'][-2:] == [built['core_sha256']] * 2
    assert not built['seed_archive']['cache_hit'] and built['seed_sha256'] == pin['g2_sha256']
    subprocess.run(cmd, check=True)
    cached = json.loads((toolchain / 'build.json').read_bytes())
    assert cached['seed_archive']['cache_hit'] and cached['core_sha256'] == built['core_sha256']
