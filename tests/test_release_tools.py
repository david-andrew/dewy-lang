"""Release tooling: the channel pointer format, CI certification and asset assembly."""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

import pytest

from tools.compiler import channel, release
from tools.compiler.package import package

ROOT = Path(__file__).resolve().parents[1]
SHA = 'c0ffee' + '0' * 34
TAG = f'dewy-0.0.0-dev.20261020.{SHA[:12]}'
VERSION = (ROOT / 'VERSION').read_text().strip()


def sums_for(names=channel.ASSETS) -> dict[str, str]:
    return {name: hashlib.sha256(name.encode()).hexdigest() for name in names}


def test_channel_round_trip():
    text = channel.render(TAG, sums_for())
    assert text.splitlines()[:2] == ['dewy-toolchain-channel 1', f'release {TAG}']
    assert text.endswith('\nend\n') and text.isascii()
    assert channel.parse(text) == (TAG, sums_for())
    sums_text = ''.join(f'{sha}  {name}\n' for name, sha in sums_for().items())
    assert channel.channel_for('unused/repo', TAG, sums_text) == text


@pytest.mark.parametrize('text', [
    '',
    'dewy-toolchain-channel 1\nrelease x\nend\n',
    f'dewy-toolchain-channel 1\nrelease {TAG}\nend\n',
    f'dewy-toolchain-channel 1\r\nrelease {TAG}\r\nsha256 {"0" * 64} a\r\nend\r\n',
    f'dewy-toolchain-channel 1\nrelease {TAG}\nsha256 {"0" * 64} a\nsha256 {"0" * 64} a\nend\n',
    f'dewy-toolchain-channel 1\nrelease {TAG}\nsha256 {"0" * 64} ../a\nend\n',
    f'dewy-toolchain-channel 1\nrelease {TAG}\nsha256  {"0" * 64} a\nend\n',
    f'dewy-toolchain-channel 1\nrelease {TAG}\nsha256 {"0" * 64} a\nend',
])
def test_channel_rejects_malformed_text(text):
    with pytest.raises(channel.ChannelError):
        channel.parse(text)


def test_channel_requires_every_asset():
    with pytest.raises(channel.ChannelError, match='install.ps1'):
        channel.render(TAG, sums_for(channel.ASSETS[:-1]))
    with pytest.raises(channel.ChannelError):
        channel.render('native-15e579752bd7', sums_for())
    with pytest.raises(channel.ChannelError):
        channel.parse_sums('0' * 64 + ' install.sh\n')


def test_tag_is_derived_from_the_commit():
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()
    tag = release.tag_for(head)
    assert re.fullmatch(rf'dewy-0\.0\.0-dev\.\d{{8}}\.{head[:12]}', tag) and channel.TAG.fullmatch(tag)
    assert release.tag_for(head) == tag
    with pytest.raises(release.ReleaseError):
        release.tag_for(head[:12])


def ci_run(run_id, *, number=1, event='push', conclusion='success', sha=SHA):
    return {'id': run_id, 'run_number': number, 'event': event, 'conclusion': conclusion,
            'head_sha': sha, 'path': '.github/workflows/ci.yml'}


def ci_jobs(*, skip=(), fail=()):
    names = ['bootstrap-and-test', 'compile-speed',
             'host-smoke (windows, windows-latest, .exe, windows-x86_64)',
             'host-smoke (macos, macos-15, , macos-arm64)',
             'host-smoke (linux-arm64, ubuntu-24.04-arm, , linux-arm64)']
    return [{'name': n, 'conclusion': 'failure' if n in fail else 'success'} for n in names if n not in skip]


def ci_artifacts(*, expired=()):
    return [{'name': f'dewy-core-{p}-{SHA}', 'expired': p in expired} for p in channel.PLATFORMS]


def test_certification_requires_every_job_and_artifact():
    runs = [ci_run(1, number=1), ci_run(2, number=2)]
    assert release.certified_run(SHA, runs, {1: ci_jobs(), 2: ci_jobs()},
                                 {1: ci_artifacts(), 2: ci_artifacts()}) == 2
    assert release.certified_run(SHA, runs, {1: ci_jobs(), 2: ci_jobs(fail={'compile-speed'})},
                                 {1: ci_artifacts(), 2: ci_artifacts()}) == 1
    cases = [
        ([ci_run(1)], {1: ci_jobs(skip={'compile-speed'})}, {1: ci_artifacts()}, 'compile-speed missing'),
        ([ci_run(1)], {1: ci_jobs(skip={'host-smoke (macos, macos-15, , macos-arm64)'})}, {1: ci_artifacts()},
         'host-smoke macos-arm64 missing'),
        ([ci_run(1)], {1: ci_jobs()}, {1: ci_artifacts(expired={'linux-arm64'})}, 'linux-arm64'),
        ([ci_run(1, event='workflow_dispatch')], {1: ci_jobs()}, {1: ci_artifacts()}, 'no successful'),
        ([ci_run(1, conclusion='failure')], {1: ci_jobs()}, {1: ci_artifacts()}, 'no successful'),
        ([ci_run(1, sha='1' * 40)], {1: ci_jobs()}, {1: ci_artifacts()}, 'no successful'),
    ]
    for runs, jobs, artifacts, reason in cases:
        with pytest.raises(release.ReleaseError, match=reason):
            release.certified_run(SHA, runs, jobs, artifacts)


def fake_toolchain(directory: Path, host: str) -> Path:
    """A toolchain directory with the provenance files package.py verifies."""
    binary = 'bin/dewy-core.exe' if host == 'windows' else 'bin/dewy-core'
    files = {binary: f'compiler for {host}\n'.encode(), 'lib/core/rt.jo': b'# runtime\n',
             'lib/std/list.jo': b'# list\n', 'LICENSE': b'license\n', 'NOTICE': b'notice\n'}
    for name, data in files.items():
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(data)
    sha = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    build = {'core_sha256': sha[binary], 'sources_sha256': {n: s for n, s in sha.items() if n != binary}}
    if host == 'linux-x86_64':
        (directory / 'build.json').write_text(json.dumps(build))
    else:
        (directory / 'HOST_BUILD.json').write_text(json.dumps(
            {'host': host, 'compiler_sha256': sha[binary], 'source_build': build}))
    return directory


@pytest.fixture
def artifacts(tmp_path):
    root = tmp_path / 'artifacts'
    for platform in channel.PLATFORMS:
        toolchain = fake_toolchain(tmp_path / 'toolchains' / platform, release.HOST_FOR[platform])
        (root / platform).mkdir(parents=True)
        package(toolchain, root / platform / f'dewy-core-{platform}.tar.gz', revision=SHA)
    return root


def test_assemble_verifies_and_lays_out_every_asset(artifacts, tmp_path, monkeypatch):
    monkeypatch.setattr(release, 'version_at', lambda sha: VERSION)
    dist = tmp_path / 'dist'
    release.assemble(SHA, artifacts, dist, installers=ROOT)
    names = sorted(p.name for p in dist.iterdir())
    assert names == sorted([*channel.ASSETS, *(f'{a}.sha256' for a in channel.ARCHIVES), 'SHA256SUMS'])
    sums = channel.parse_sums((dist / 'SHA256SUMS').read_text())
    assert list(sums) == list(channel.ASSETS)
    assert channel.parse(channel.channel_for('unused/repo', TAG, (dist / 'SHA256SUMS').read_text()))[1] == sums
    downloaded = tmp_path / 'downloaded'
    downloaded.mkdir()
    for path in dist.iterdir():
        (downloaded / path.name).write_bytes(path.read_bytes())
    release.compare(dist, downloaded)
    (downloaded / 'install.sh').write_text('#!/bin/sh\n')
    with pytest.raises(release.ReleaseError, match='install.sh'):
        release.compare(dist, downloaded)


def rewrite(archive: Path, change) -> None:
    """Rewrite a package's members through `change(name, data) -> data | None` and refresh its sidecar."""
    with tarfile.open(archive) as source:
        members = [(m, source.extractfile(m).read()) for m in source.getmembers()]
    with tarfile.open(archive, 'w:gz') as target:
        for member, data in members:
            data = change(member.name, data)
            if data is not None:
                member.size = len(data)
                target.addfile(member, io.BytesIO(data))
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + '.sha256').write_text(f'{sha}  {archive.name}\n')


@pytest.mark.parametrize('defect,reason', [
    ('revision', 'revision'),
    ('payload', 'does not match PACKAGE.json'),
    ('extra', 'payload differs'),
    ('release', 'RELEASE does not match PACKAGE.json'),
    ('sidecar', 'sidecar'),
    ('version', 'RELEASE does not identify'),
])
def test_assemble_rejects_packages_that_differ_from_ci(artifacts, tmp_path, defect, reason):
    archive = artifacts / 'linux-arm64' / 'dewy-core-linux-arm64.tar.gz'
    version = VERSION
    if defect == 'revision':
        rewrite(archive, lambda n, d: d.replace(SHA.encode(), b'1' * 40) if n.endswith('PACKAGE.json') else d)
    elif defect == 'payload':
        rewrite(archive, lambda n, d: d + b'changed' if n.endswith('rt.jo') else d)
    elif defect == 'extra':
        rewrite(archive, lambda n, d: d)
        with tarfile.open(archive) as source:
            members = [(m, source.extractfile(m).read()) for m in source.getmembers()]
        with tarfile.open(archive, 'w:gz') as target:
            for member, data in members:
                target.addfile(member, io.BytesIO(data))
            extra = tarfile.TarInfo('dewy-core/extra')
            target.addfile(extra, io.BytesIO(b''))
        rewrite(archive, lambda n, d: d)
    elif defect == 'release':
        rewrite(archive, lambda n, d: d.replace(b'linux-arm64', b'linux-x86_64') if n.endswith('RELEASE') else d)
    elif defect == 'sidecar':
        archive.with_name(archive.name + '.sha256').write_text(f'{"0" * 64}  {archive.name}\n')
    elif defect == 'version':
        version = '0.0.1-dev.0'
    with pytest.raises(release.ReleaseError, match=reason):
        release.check_archive(archive, SHA, 'linux-arm64', version)


def test_assemble_rejects_a_package_for_another_host(artifacts):
    archive = artifacts / 'macos-arm64' / 'dewy-core-macos-arm64.tar.gz'
    with pytest.raises(release.ReleaseError, match='not a linux-arm64 package'):
        release.check_archive(archive, SHA, 'linux-arm64', VERSION)
