"""The checked-in historical Jo capsule and its native G2 are independent pins."""
import json
import platform
import shutil
import subprocess

import pytest

from tools.compiler import seed_archive as seed


def manifest():
    return json.loads((seed.PIN / 'pin.json').read_bytes())


def test_pin_matches_every_ordered_member(tmp_path):
    pin = manifest()
    data = seed.checked(seed.PIN / seed.ARCHIVE, pin['archive_sha256'])
    members = json.loads(seed.checked(seed.PIN / seed.INVENTORY, pin['members_sha256']))
    seed.checked(seed.PIN / seed.RECIPE, pin['recipe_sha256'])
    seed.extract(data, members, tmp_path)
    assert (tmp_path / 'LICENSE').read_bytes() == (seed.ROOT / 'LICENSE').read_bytes()
    assert pin['license'] == 'Apache-2.0 WITH LLVM-exception'
    assert (tmp_path / 'stage0/main.c').is_file() and (tmp_path / 'compiler/main.jo').is_file()
    member = 'compiler/main.jo'
    members[member] = '0' * 64
    with pytest.raises(RuntimeError, match=member):
        seed.extract(data, members, tmp_path / 'altered')


@pytest.mark.nightly
def test_recreate_capsule_twice_from_clean_trees(tmp_path):
    revision = manifest()['revision']
    if subprocess.run(['git', 'cat-file', '-e', revision], cwd=seed.ROOT, check=False).returncode:
        pytest.skip('pin revision is outside the clone history')
    for run in ('first', 'second'):
        repo = tmp_path / run
        subprocess.run(['git', 'init', '-q', repo], check=True)
        subprocess.run(['git', 'fetch', '-q', '--depth=1', seed.ROOT.as_uri(), revision], cwd=repo, check=True)
        subprocess.run(['git', 'checkout', '-q', '--detach', 'FETCH_HEAD'], cwd=repo, check=True)
        dest = tmp_path / (run + '-archive')
        seed.generate(repo, revision, dest)
        for name in (seed.ARCHIVE, seed.INVENTORY):
            assert (dest / name).read_bytes() == (seed.PIN / name).read_bytes()


native_host = pytest.mark.skipif((platform.system(), platform.machine()) != ('Linux', 'x86_64'),
                                 reason='the native G2 pin is for Linux x86-64')


@native_host
@pytest.mark.parametrize('damaged', [seed.ARCHIVE, seed.RECIPE, seed.INVENTORY, seed.G2])
def test_reject_damaged_inputs_even_on_a_cache_hit(tmp_path, damaged):
    pin_dir = tmp_path / 'pin'
    shutil.copytree(seed.PIN, pin_dir)
    pin = manifest()
    cache = tmp_path / 'cache'
    cached = cache / pin['host'] / pin['recipe_sha256'] / pin['archive_sha256'] / seed.G2
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b'damaged G2')
    if damaged != seed.G2:
        (pin_dir / damaged).write_bytes(b'damaged input')
    with pytest.raises(RuntimeError, match=f'SHA-256 mismatch for .*{damaged}'):
        seed.obtain(cache, pin_dir)


@native_host
@pytest.mark.nightly
def test_clean_c_chain_then_verified_cache_hit(tmp_path):
    binary, cold = seed.obtain(tmp_path)
    assert not cold['cache_hit']
    assert cold['built_sha256']['bin/' + seed.G2] == manifest()['g2_sha256']
    before = binary.stat()
    same, hit = seed.obtain(tmp_path)
    assert same == binary and hit['cache_hit']
    assert same.stat().st_ino == before.st_ino and same.stat().st_mtime_ns == before.st_mtime_ns
