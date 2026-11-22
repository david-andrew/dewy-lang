"""The archive route builds only live inputs after G2 and checks adjacent live generations."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import core
from tools.compiler import build as builder


@pytest.mark.parametrize('contents', [
    [b'current', b'current'],
    [b'older', b'current', b'current'],
    [b'older', b'currentA', b'currentB'],
])
def test_archive_generations_and_provenance(tmp_path, monkeypatch, contents):
    source = tmp_path / 'checkout'
    for name in ('compiler/main.jo', 'lib/core/rt.jo', 'LICENSE'):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    archive_seed = tmp_path / 'cached-g2'
    archive_seed.write_bytes(b'g2')
    pin = {'cache_hit': True, 'g2_sha256': builder.identity(archive_seed)}
    monkeypatch.setattr(builder, 'ROOT', source)
    monkeypatch.setattr(builder.seed_archive, 'obtain', lambda cache, **kwargs: (archive_seed, pin))
    monkeypatch.setattr(builder, 'use_frozen_twins', lambda *args: pytest.fail('touched live twins'))
    output = tmp_path / 'live'
    binary = output / 'bin/dewy-core'
    calls = []

    def compile(command, *, cwd, env, **kwargs):
        compiler, verb, main, flag, target = command
        generation = len(calls)
        assert Path(compiler).read_bytes() == (contents[generation - 1] if generation else b'g2')
        assert (verb, main, flag, target) == ('build', output / 'compiler/main.jo', '-o', binary)
        assert cwd == output and env['DEWY_CORE_LIB'] == str(output / 'lib')
        calls.append(compiler)
        target.write_bytes(contents[generation])
        return SimpleNamespace(stdout='', stderr='', returncode=0)

    monkeypatch.setattr(builder.subprocess, 'run', compile)
    if contents[-2] != contents[-1]:
        with pytest.raises(RuntimeError, match=r'not a fixed point: .*byte offset 7'):
            builder.build(output, bootstrap_archive=True)
        assert binary.with_suffix('.generation-n').read_bytes() == contents[-2]
        assert not (output / 'build.json').exists()
    else:
        assert builder.build(output, bootstrap_archive=True) == binary
        info = json.loads((output / 'build.json').read_bytes())
        assert info['seed_archive'] == pin and info['seed_sha256'] == pin['g2_sha256']
        assert info['live_generations_sha256'] == [builder.seed_archive.sha(data) for data in contents]
        assert info['core_sha256'] == info['live_generations_sha256'][-1]
        assert set(info['sources_sha256']) == {str(path.relative_to(source)) for path in source.rglob('*') if path.is_file()}
        assert len(info['build_steps']) == len(contents)
    assert len(calls) == len(contents) and binary.read_bytes() == contents[-1]


def test_core_forces_archive_route_and_tracks_its_inputs(tmp_path, monkeypatch):
    source = tmp_path / 'checkout'
    seed_cache = tmp_path / 'pins'
    files = ['LICENSE', 'tools/compiler/build.py', 'tools/compiler/seed_archive.py',
             'bootstrap-seed/pin.json', 'bootstrap-seed/source.tar.xz',
             'bootstrap-seed/members.json', 'bootstrap-seed/build-g2.sh']
    for name in files:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    assert core.source_paths(source) == sorted(source / name for name in files)
    outputs = []

    def build(output, *, bootstrap_archive, seed_cache):
        assert bootstrap_archive and seed_cache == tmp_path / 'pins'
        binary = output / 'bin/dewy-core'
        binary.parent.mkdir(parents=True)
        binary.write_text('verified')
        outputs.append(binary)
        return binary

    monkeypatch.setattr(core, 'build', build)
    options = {'root': source, 'cache': tmp_path / 'live-cache'}
    for _ in range(2):
        core.toolchain(bootstrap_archive=True, seed_cache=seed_cache, **options)
    assert len(set(outputs)) == 2
    assert core.toolchain(**options) == outputs[-1]
    state = json.loads((options['cache'] / 'current.json').read_bytes())
    assert state['source_identity'] == core.source_identity(source)
