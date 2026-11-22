"""Rebuild the two C lineages in separate offline roots at identical compiler paths."""
import json
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.compiler import seed_archive as seed


@pytest.mark.nightly
def test_clean_shallow_offline_clone_matches_independent_bootstrap(tmp_path):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or not shutil.which('bwrap'):
        pytest.skip('requires a Linux x86-64 host with bubblewrap for private mount and network namespaces')
    checkout = tmp_path / 'checkout'
    subprocess.run(['git', 'clone', '-q', '--depth=1', '--no-tags', seed.ROOT.as_uri(), checkout], check=True)
    assert (checkout / '.git/shallow').is_file()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout) == subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=seed.ROOT)
    pin = json.loads((checkout / 'bootstrap-seed/pin.json').read_bytes())
    target = Path(pin['comparison_root'])
    outputs = []
    for name, route in [('independent', '--bootstrap'), ('archived', '--bootstrap-archive')]:
        work = tmp_path / name
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
        cmd = [*sandbox, 'python3', 'tools/compiler/build.py', route, '--fixed-point', '--output', target]
        toolchain = work / target.name
        if route == '--bootstrap-archive':
            cmd += ['--seed-cache', target.parent / 'seed-cache']
        subprocess.run(cmd, check=True)
        built = json.loads((toolchain / 'build.json').read_bytes())
        assert built['live_generations_sha256'][-2:] == [built['core_sha256']] * 2
        outputs.append((toolchain / 'bin/dewy-core').read_bytes())
        if route == '--bootstrap-archive':
            assert not built['seed_archive']['cache_hit'] and built['seed_sha256'] == pin['g2_sha256']
            subprocess.run(cmd, check=True)
            cached = json.loads((toolchain / 'build.json').read_bytes())
            assert cached['seed_archive']['cache_hit'] and cached['core_sha256'] == built['core_sha256']
    assert outputs[0] == outputs[1]
