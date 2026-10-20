"""Installer transactions: install.sh and install.ps1 against fake releases.

Releases are directories served from the filesystem or a local HTTP server;
DEWY_INSTALL_CHANNEL_URL and DEWY_INSTALL_DOWNLOAD_URL point the installers
at them. Most install.sh checks use a shell-script stand-in for the compiler;
the end-to-end checks package the real toolchain (DEWY_CORE_COMPILER).
install.ps1 runs only on Windows (CI) apart from its host check.
"""
from __future__ import annotations

import hashlib
import http.server
import io
import json
import os
import platform
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
from pathlib import Path

import pytest

from tools.compiler import channel
from tools.compiler.package import package, release_identity

ROOT = Path(__file__).resolve().parents[1]
DATE = '20261020'
SAMPLE = 'main=()=>{let values=[20 22] return sum(values)}\n'


def host_platform() -> str | None:
    system, machine = platform.system(), platform.machine().lower()
    return {('Linux', 'x86_64'): 'linux-x86_64', ('Linux', 'amd64'): 'linux-x86_64',
            ('Linux', 'aarch64'): 'linux-arm64', ('Linux', 'arm64'): 'linux-arm64',
            ('Darwin', 'arm64'): 'macos-arm64', ('Windows', 'amd64'): 'windows-x86_64',
            ('Windows', 'x86_64'): 'windows-x86_64'}.get((system, machine))


HOST = host_platform()
# /bin/bash is bash 3.2 on macOS: the oldest shell install.sh must support.
BASH = ('/bin/bash' if os.path.exists('/bin/bash') else shutil.which('bash')) if os.name != 'nt' else None
posix_only = pytest.mark.skipif(not (BASH and shutil.which('curl') and HOST and HOST != 'windows-x86_64'),
                                reason='install.sh runs on Linux and macOS hosts with bash and curl')
POWERSHELLS = [shell for shell in ('powershell', 'pwsh') if shutil.which(shell)] if os.name == 'nt' else []
windows_only = pytest.mark.skipif(not POWERSHELLS, reason='install.ps1 runs on Windows')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revision_for(label: str) -> str:
    return hashlib.sha1(label.encode()).hexdigest()


def tag_for(revision: str) -> str:
    return f'dewy-0.0.0-dev.{DATE}.{revision[:12]}'


def fake_compiler(label: str, behavior: str = '') -> bytes:
    """A shell stand-in: --version, --print-lib, `build SRC -o OUT` (a program exiting 42)."""
    return f'''#!/bin/sh
case "$1" in
    --version) echo "dewy-core fake {label}" ;;
    --print-lib) cd "$(dirname "$0")/../lib" && pwd ;;
    build)
        {behavior}
        out=; previous=
        for argument in "$@"; do
            if [ "$previous" = -o ]; then out=$argument; fi
            previous=$argument
        done
        printf '#!/bin/sh\\nexit 42\\n' > "$out"
        chmod +x "$out" ;;
    *) echo "fake {label} ran: $*" ;;
esac
'''.encode()


def add(archive: tarfile.TarFile, name: str, data: bytes = b'', *, mode: int = 0o644,
        kind: bytes = tarfile.REGTYPE, link: str = '') -> None:
    member = tarfile.TarInfo(name)
    member.type = kind
    member.mode = mode
    member.linkname = link
    member.size = len(data) if kind == tarfile.REGTYPE else 0
    archive.addfile(member, io.BytesIO(data) if kind == tarfile.REGTYPE else None)


def fake_archive(path: Path, platform_name: str, revision: str, label: str, *,
                 behavior: str = '', defect: str = '') -> None:
    with tarfile.open(path, 'w:gz') as archive:
        binary = 'bin/dewy-core.exe' if platform_name == 'windows-x86_64' else 'bin/dewy-core'
        files = {
            binary: fake_compiler(label, behavior),
            'lib/core/rt.jo': b'# runtime\n',
            'RELEASE': release_identity('macos-arm64' if defect == 'wrong-platform' else platform_name,
                                        '0' * 40 if defect == 'wrong-revision' else revision).encode(),
            'LICENSE': b'license\n',
        }
        if defect == 'missing-lib':
            del files['lib/core/rt.jo']
        files['PACKAGE.json'] = json.dumps({'format': 1, 'revision': revision, 'files': {
            name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}).encode()
        for name, data in sorted(files.items()):
            add(archive, f'dewy-core/{name}', data, mode=0o755 if name.startswith('bin/') else 0o644)
        if defect == 'traversal':
            add(archive, 'dewy-core/../escaped', b'escaped\n')
        elif defect == 'absolute':
            add(archive, '/tmp/dewy-installer-test-escaped', b'escaped\n')
        elif defect == 'symlink':
            add(archive, 'dewy-core/lib/escape', kind=tarfile.SYMTYPE, link='../../../../escaped')
        elif defect == 'hardlink':
            add(archive, 'dewy-core/lib/same', kind=tarfile.LNKTYPE, link='dewy-core/RELEASE')
        elif defect == 'hidden':
            add(archive, 'dewy-core/.hidden', b'hidden\n')
    if defect == 'not-gzip':
        path.write_bytes(b'not an archive\n' * 100)


class Releases:
    """A release download root (<root>/<tag>/<asset>) and a channel file."""

    def __init__(self, root: Path):
        self.root = root / 'served'
        self.root.mkdir(parents=True)
        self.channel = root / 'toolchain-channel.txt'

    def publish(self, label: str, *, archive=None, revision: str | None = None, **fake) -> str:
        revision = revision or revision_for(label)
        tag = tag_for(revision)
        directory = self.root / tag
        directory.mkdir()
        for platform_name in channel.PLATFORMS:
            asset = directory / f'dewy-core-{platform_name}.tar.gz'
            if archive is not None:
                archive(asset, platform_name, revision)
            else:
                fake_archive(asset, platform_name, revision, label, **fake)
            asset.with_name(asset.name + '.sha256').write_text(f'{sha256(asset)}  {asset.name}\n')
        for name in channel.INSTALLERS:
            shutil.copyfile(ROOT / name, directory / name)
        (directory / 'SHA256SUMS').write_text(
            ''.join(f'{sha256(directory / name)}  {name}\n' for name in channel.ASSETS))
        return tag

    def point(self, tag: str) -> None:
        sums = channel.parse_sums((self.root / tag / 'SHA256SUMS').read_text())
        self.channel.write_text(channel.render(tag, sums), newline='\n')


class Server:
    """Serves a directory over HTTP; can stall a file after half of its bytes."""

    def __init__(self, root: Path):
        self.root = root
        self.stall: set[str] = set()
        self.stalled = threading.Event()
        self.resume = threading.Event()
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                path = server.root / urllib.parse.unquote(self.path.split('?')[0].lstrip('/'))
                if not path.is_file():
                    self.send_error(404)
                    return
                data = path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                if path.name in server.stall:
                    self.wfile.write(data[:len(data) // 2])
                    self.wfile.flush()
                    server.stalled.set()
                    server.resume.wait(60)
                    return
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.httpd.server_address[1]}'

    def close(self):
        self.resume.set()
        self.httpd.shutdown()
        self.httpd.server_close()


def snapshot(*roots: Path) -> dict:
    state = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                state[str(path)] = ('link', os.readlink(path))
            elif path.is_file():
                state[str(path)] = ('file', sha256(path), stat.S_IMODE(path.stat().st_mode))
            else:
                state[str(path)] = ('dir',)
    return state


# ---------------------------------------------------------------- install.sh

@pytest.fixture
def world(tmp_path):
    """A home directory with spaces, a fake release root and installer environment."""
    releases = Releases(tmp_path)
    home = tmp_path / 'home with spaces'
    home.mkdir()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('DEWY_', 'SLOPPY_')) and k not in ('ZDOTDIR', 'XDG_CONFIG_HOME')}
    env.update(HOME=str(home), SHELL='/bin/bash',
               DEWY_INSTALL_CHANNEL_URL=releases.channel.as_uri(),
               DEWY_INSTALL_DOWNLOAD_URL=releases.root.as_uri())

    class World:
        pass
    w = World()
    w.tmp, w.home, w.releases, w.env = tmp_path, home, releases, env
    w.prefix = home / '.dewy'
    return w


def install(world, *args, env=None, check=True, script=None, stdin=None):
    command = [BASH, str(script or ROOT / 'install.sh'), *args] if stdin is None else [BASH, '-s', '--', *args]
    result = subprocess.run(command, env=env or world.env, input=stdin, capture_output=True,
                            text=True, timeout=120, check=False)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def launch(prefix: Path, *args, env=None, name='dewy', cwd=None, check=True):
    result = subprocess.run([str(prefix / 'bin' / name), *args], env=env, capture_output=True,
                            text=True, timeout=120, check=False, cwd=cwd)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def pointer(prefix: Path) -> list[str]:
    return (prefix / 'toolchains/current').read_text().splitlines()


def toolchains(prefix: Path) -> list[str]:
    return sorted(p.name for p in (prefix / 'toolchains').iterdir() if p.is_dir() and not p.name.startswith('.'))


@posix_only
def test_install_update_and_rollback(world):
    a = world.releases.publish('a')
    world.releases.point(a)
    out = install(world).stdout
    assert f'Installed Dewy toolchain {a}' in out and revision_for('a') in out
    assert pointer(world.prefix) == [a, '']
    assert launch(world.prefix, '--version', env=world.env).stdout == 'dewy-core fake a\n'
    assert launch(world.prefix, '--version', name='dewy-core', env=world.env).stdout == 'dewy-core fake a\n'
    # Ordinary arguments reach the versioned compiler unchanged.
    assert launch(world.prefix, 'run', 'my program.dewy', env=world.env).stdout == 'fake a ran: run my program.dewy\n'
    assert launch(world.prefix, '--print-lib', env=world.env).stdout.strip() == str(world.prefix / 'toolchains' / a / 'lib')

    b = world.releases.publish('b')
    world.releases.point(b)
    launch(world.prefix, 'update', env=world.env)
    assert pointer(world.prefix) == [b, a]
    assert launch(world.prefix, '--version', env=world.env).stdout == 'dewy-core fake b\n'
    assert 'up to date' in launch(world.prefix, 'update', env=world.env).stdout
    assert pointer(world.prefix) == [b, a]

    assert f'Rolled back to {a}' in launch(world.prefix, 'rollback', env=world.env).stdout
    assert pointer(world.prefix) == [a, b]
    assert launch(world.prefix, '--version', env=world.env).stdout == 'dewy-core fake a\n'
    launch(world.prefix, 'rollback', name='dewy-core', env=world.env)
    assert pointer(world.prefix) == [b, a]

    # One previous generation is kept; older toolchains are removed.
    c = world.releases.publish('c')
    launch(world.prefix, 'update', '--release', c, env=world.env)
    assert pointer(world.prefix) == [c, b]
    assert toolchains(world.prefix) == sorted([b, c])
    assert not [p for p in (world.prefix / 'toolchains').iterdir() if p.name.startswith(('.staging', '.trash'))]
    assert launch(world.prefix, 'rollback', env=world.env).returncode == 0
    assert launch(world.prefix, 'rollback', env=world.env).returncode == 0
    # The stored updater is the verified installer of the release.
    assert sha256(world.prefix / 'libexec/dewy-install.sh') == sha256(ROOT / 'install.sh')


@posix_only
def test_rollback_without_previous_fails(world):
    a = world.releases.publish('a')
    world.releases.point(a)
    install(world)
    result = launch(world.prefix, 'rollback', env=world.env, check=False)
    assert result.returncode != 0 and 'no previous toolchain' in result.stderr
    assert pointer(world.prefix) == [a, '']


@posix_only
def test_piped_install_of_an_explicit_release(world):
    a = world.releases.publish('a')
    world.releases.channel.write_text('not a channel\n')  # --release bypasses the channel
    install(world, '--release', a, '--no-modify-path', stdin=(ROOT / 'install.sh').read_text())
    assert pointer(world.prefix) == [a, '']
    assert not (world.home / '.bashrc').exists()
    bad = install(world, '--release', 'native-15e579752bd7', check=False)
    assert bad.returncode != 0 and 'not a Dewy toolchain release tag' in bad.stderr


DEFECTS = ['checksum', 'traversal', 'absolute', 'symlink', 'hardlink', 'hidden', 'not-gzip',
           'wrong-platform', 'wrong-revision', 'missing-lib', 'smoke-fails']


@posix_only
@pytest.mark.parametrize('defect', DEFECTS)
def test_rejects_defective_release(world, defect):
    a = world.releases.publish('a')
    world.releases.point(a)
    install(world)
    before = snapshot(world.home)
    if defect == 'smoke-fails':
        b = world.releases.publish('b', behavior='exit 3')
    else:
        b = world.releases.publish('b', defect='' if defect == 'checksum' else defect)
    world.releases.point(b)
    if defect == 'checksum':
        asset = world.releases.root / b / f'dewy-core-{HOST}.tar.gz'
        fake_archive(asset, HOST, revision_for('b'), 'tampered')
    result = install(world, check=False)
    assert result.returncode != 0, result.stdout
    assert 'nothing was changed' in result.stderr or 'contains' in result.stderr or 'readable' in result.stderr, result.stderr
    assert snapshot(world.home) == before
    assert not (world.tmp / 'escaped').exists() and not (world.home / 'escaped').exists()
    assert launch(world.prefix, '--version', env=world.env).stdout == 'dewy-core fake a\n'


CHANNELS = {
    'crlf': lambda text: text.replace('\n', '\r\n'),
    'truncated': lambda text: text.replace('end\n', ''),
    'no-final-newline': lambda text: text[:-1],
    'trailing-line': lambda text: text + 'release x\n',
    'future-version': lambda text: text.replace('channel 1', 'channel 2'),
    'bad-tag': lambda text: text.replace('release dewy-0.0.0', 'release native-0.0.0'),
    'bad-digest': lambda text: text.replace('sha256 ', 'sha256 Z', 1),
    'injection': lambda text: text.replace('release ', 'release $(touch pwned) ', 1),
    'unknown-line': lambda text: text.replace('end\n', 'url https://example.com\nend\n'),
    'empty': lambda text: '',
}


@posix_only
@pytest.mark.parametrize('corruption', sorted(CHANNELS))
def test_rejects_invalid_channel(world, corruption):
    a = world.releases.publish('a')
    world.releases.point(a)
    install(world)
    before = snapshot(world.home)
    b = world.releases.publish('b')
    world.releases.point(b)
    text = CHANNELS[corruption](world.releases.channel.read_text())
    world.releases.channel.write_bytes(text.encode())
    with pytest.raises(channel.ChannelError):
        channel.parse(text)
    result = install(world, check=False)
    assert result.returncode != 0 and 'invalid toolchain channel' in result.stderr, result.stderr
    assert snapshot(world.home) == before
    assert not list(world.tmp.rglob('pwned'))


@posix_only
@pytest.mark.parametrize('system,machine', [('Darwin', 'x86_64'), ('FreeBSD', 'amd64'),
                                            ('Linux', 'riscv64'), ('Linux', 'armv7l'),
                                            ('MINGW64_NT-10.0-19045', 'x86_64')])
def test_rejects_unsupported_hosts_before_changes(world, system, machine):
    fake = world.tmp / 'fake-host'
    fake.mkdir()
    (fake / 'uname').write_text(f'#!/bin/sh\ncase "$1" in -m) echo {machine} ;; *) echo {system} ;; esac\n')
    (fake / 'sysctl').write_text('#!/bin/sh\necho 0\n')
    for tool in fake.iterdir():
        tool.chmod(0o755)
    env = dict(world.env, PATH=f'{fake}{os.pathsep}{world.env["PATH"]}')
    a = world.releases.publish('a')
    world.releases.point(a)
    result = install(world, env=env, check=False)
    assert result.returncode != 0
    assert 'not supported' in result.stderr or 'unsupported host' in result.stderr
    assert list(world.home.iterdir()) == []


@posix_only
def test_interrupted_download_keeps_previous_toolchain(world):
    server = Server(world.releases.root.parent)
    try:
        env = dict(world.env, DEWY_INSTALL_CHANNEL_URL=f'{server.url}/toolchain-channel.txt',
                   DEWY_INSTALL_DOWNLOAD_URL=f'{server.url}/served')
        a = world.releases.publish('a')
        world.releases.point(a)
        install(world, env=env)
        b = world.releases.publish('b')
        world.releases.point(b)
        server.stall.add(f'dewy-core-{HOST}.tar.gz')
        process = subprocess.Popen([BASH, str(ROOT / 'install.sh')], env=env, start_new_session=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert server.stalled.wait(60)
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(30)
        assert pointer(world.prefix) == [a, '']
        assert launch(world.prefix, '--version', env=env).stdout == 'dewy-core fake a\n'
        assert (world.prefix / 'toolchains/.lock').is_dir()  # left by the killed installer
        server.stall.clear()
        install(world, env=env)  # recovers the stale lock and staging directory
        assert pointer(world.prefix) == [b, a]
        assert not [p for p in (world.prefix / 'toolchains').iterdir() if p.name.startswith('.')]
    finally:
        server.close()


@posix_only
def test_interrupted_smoke_test_keeps_previous_toolchain(world):
    a = world.releases.publish('a')
    world.releases.point(a)
    install(world)
    marker = world.tmp / 'smoke-started'
    b = world.releases.publish('b', behavior=f": > '{marker}'; sleep 60")
    world.releases.point(b)
    process = subprocess.Popen([BASH, str(ROOT / 'install.sh')], env=world.env, start_new_session=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 60
    while not marker.exists():
        assert time.monotonic() < deadline and process.poll() is None
        time.sleep(0.05)
    os.killpg(process.pid, signal.SIGKILL)
    process.wait(30)
    assert pointer(world.prefix) == [a, '']
    assert toolchains(world.prefix) == [a]
    assert launch(world.prefix, '--version', env=world.env).stdout == 'dewy-core fake a\n'


@posix_only
def test_interruption_at_any_point_leaves_a_working_toolchain(world):
    a = world.releases.publish('a')
    b = world.releases.publish('b')
    world.releases.point(a)
    install(world)
    world.releases.point(b)
    started = time.monotonic()
    install(world)
    duration = time.monotonic() - started
    launch(world.prefix, 'rollback', env=world.env)
    for step in range(10):
        process = subprocess.Popen([BASH, str(ROOT / 'install.sh')], env=world.env, start_new_session=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(duration * step / 10)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(30)
        assert pointer(world.prefix)[0] in (a, b)
        version = launch(world.prefix, '--version', env=world.env).stdout
        assert version in ('dewy-core fake a\n', 'dewy-core fake b\n')
        if pointer(world.prefix)[0] == b:
            launch(world.prefix, 'rollback', env=world.env)
    install(world)
    assert pointer(world.prefix) == [b, a]
    assert not [p for p in (world.prefix / 'toolchains').iterdir() if p.name.startswith('.')]
    assert sorted(p.name for p in (world.prefix / 'bin').iterdir()) == ['dewy', 'dewy-core', 'udewy']
    assert [p.name for p in (world.prefix / 'libexec').iterdir()] == ['dewy-install.sh']


@posix_only
def test_waits_for_a_running_installer(world):
    a = world.releases.publish('a')
    world.releases.point(a)
    lock = world.prefix / 'toolchains/.lock'
    lock.mkdir(parents=True)
    holder = subprocess.Popen(['sleep', '60'])
    try:
        (lock / 'pid').write_text(f'{holder.pid}\n')
        process = subprocess.Popen([BASH, str(ROOT / 'install.sh')], env=world.env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1.5)
        assert process.poll() is None and not (world.prefix / 'toolchains/current').exists()
        holder.kill()
        holder.wait()
        out, err = process.communicate(timeout=60)
        assert process.returncode == 0, out + err
        assert 'Waiting for another Dewy installation' in out
        assert pointer(world.prefix) == [a, '']
    finally:
        holder.kill()


@posix_only
def test_prefix_with_spaces_and_quotes(world):
    a = world.releases.publish('a')
    world.releases.point(a)
    prefix = world.tmp / "it's a $dir" / 'dewy home'
    env = dict(world.env, SHELL='/usr/bin/zsh')
    install(world, '--prefix', str(prefix), env=env)
    assert pointer(prefix) == [a, '']
    assert launch(prefix, '--version', env=env).stdout == 'dewy-core fake a\n'
    assert launch(prefix, 'rollback', env=env, check=False).returncode != 0
    for rc in ('.zshrc', '.zprofile'):
        shown = subprocess.run(['sh', '-c', '. "$1"; printf %s "$PATH"', 'sh', str(world.home / rc)],
                               env=env, capture_output=True, text=True, check=True).stdout
        assert shown.split(':')[0] == str(prefix / 'bin')
    assert not world.prefix.exists()


@posix_only
def test_path_blocks_are_idempotent(world):
    a = world.releases.publish('a')
    world.releases.point(a)
    bashrc = world.home / '.bashrc'
    bashrc.write_text('alias ll="ls -l"\n')
    (world.home / '.bash_profile').write_text('. ~/.bashrc\n')
    install(world)
    install(world)
    for rc in (bashrc, world.home / '.bash_profile'):
        text = rc.read_text()
        assert text.count('# >>> dewy toolchain >>>') == 1 and text.count('# <<< dewy toolchain <<<') == 1
    assert bashrc.read_text().startswith('alias ll="ls -l"\n\n# >>> dewy toolchain >>>')
    before = snapshot(world.home)
    install(world, '--no-modify-path')
    assert snapshot(world.home) == before
    fish = dict(world.env, SHELL='/usr/bin/fish')
    install(world, env=fish)
    config = (world.home / '.config/fish/config.fish').read_text()
    assert f"set -gx PATH '{world.prefix / 'bin'}' $PATH" in config


@posix_only
def test_legacy_installation_is_preserved(world):
    legacy = world.prefix
    release = legacy / 'releases' / ('f' * 64)
    (release / 'library').mkdir(parents=True)
    (release / 'library/path.dewy').write_text('legacy library\n')
    for name in ('dewy', 'udewy'):
        (release / name).write_text(f'#!/bin/sh\necho legacy {name}\n')
        (release / name).chmod(0o755)
    (legacy / 'current').symlink_to(f'releases/{"f" * 64}')
    for name in ('dewy', 'udewy'):
        (legacy / name).symlink_to(f'current/{name}')
    (world.home / '.bashrc').write_text(
        f'\n# Include dewy tools in PATH\nif [ -d "{legacy}" ]; then\n  PATH="{legacy}:$PATH"\nfi\n')
    legacy_state = snapshot(legacy)
    a = world.releases.publish('a')
    world.releases.point(a)
    out = install(world).stdout
    assert 'legacy installation' in out
    after = snapshot(legacy)
    assert {k: v for k, v in after.items() if k in legacy_state} == legacy_state
    # The new launchers win on PATH, even when the legacy line runs again.
    shell = subprocess.run(
        [BASH, '--norc', '--noprofile', '-c',
         '. "$HOME/.bashrc"; . "$HOME/.bashrc"; command -v dewy; command -v udewy; dewy --version; udewy; echo "udewy $?"'],
        env=dict(world.env, PATH='/usr/bin:/bin'), capture_output=True, text=True, timeout=60)
    lines = shell.stdout.splitlines()
    assert lines[:3] == [str(world.prefix / 'bin/dewy'), str(world.prefix / 'bin/udewy'), 'dewy-core fake a']
    assert lines[3] == 'udewy 1'
    assert 'retired' in shell.stderr and str(legacy / 'udewy') in shell.stderr
    assert subprocess.run([str(legacy / 'udewy')], capture_output=True, text=True).stdout == 'legacy udewy\n'


@pytest.fixture(scope='module')
def real_toolchain():
    compiler = os.environ.get('DEWY_CORE_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_CORE_COMPILER for end-to-end installer checks')
    return Path(compiler).resolve(strict=True).parent.parent


def real_archive(toolchain: Path):
    def make(path: Path, platform_name: str, revision: str):
        if platform_name == HOST:
            package(toolchain, path, revision=revision)
        else:
            path.write_bytes(b'other platform\n')
    return make


@posix_only
def test_real_toolchain_over_http(world, real_toolchain):
    server = Server(world.releases.root.parent)
    try:
        env = dict(world.env, DEWY_INSTALL_CHANNEL_URL=f'{server.url}/toolchain-channel.txt',
                   DEWY_INSTALL_DOWNLOAD_URL=f'{server.url}/served')
        a = world.releases.publish('real a', archive=real_archive(real_toolchain))
        world.releases.point(a)
        install(world, env=env)
        work = world.tmp / 'my project'
        work.mkdir()
        (work / 'main.dewy').write_text(SAMPLE)
        clean = {k: v for k, v in env.items() if k != 'PATH'} | {'PATH': '/usr/bin:/bin'}
        launch(world.prefix, 'build', 'main.dewy', '-o', 'main', env=clean, cwd=work)
        assert subprocess.run([str(work / 'main')], cwd=work).returncode == 42
        assert launch(world.prefix, 'main.dewy', env=clean, cwd=work, check=False).returncode == 42
        lib = launch(world.prefix, '--print-lib', env=clean).stdout.strip()
        assert lib == str(world.prefix / 'toolchains' / a / 'lib')
        b = world.releases.publish('real b', archive=real_archive(real_toolchain))
        world.releases.point(b)
        launch(world.prefix, 'update', env=env)
        assert pointer(world.prefix) == [b, a]
        launch(world.prefix, 'rollback', env=env)
        assert pointer(world.prefix) == [a, b]
        assert launch(world.prefix, '--version', env=clean).stdout.startswith('dewy-core ')
    finally:
        server.close()


# --------------------------------------------------------------- install.ps1

def powershell(shell: str, *args, env, check=True):
    result = subprocess.run([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'install.ps1'), *args],
                            env=env, capture_output=True, text=True, timeout=300, check=False)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.mark.skipif(not (shutil.which('pwsh') or POWERSHELLS), reason='needs PowerShell')
def test_powershell_rejects_unsupported_hosts(tmp_path):
    shell = POWERSHELLS[0] if POWERSHELLS else shutil.which('pwsh')
    env = dict(os.environ, PROCESSOR_ARCHITECTURE='ARM64')
    env.pop('PROCESSOR_ARCHITEW6432', None)
    prefix = tmp_path / 'dewy home'
    result = powershell(shell, '-Prefix', str(prefix), '-NoModifyPath', env=env, check=False)
    assert result.returncode != 0
    assert 'unsupported host' in result.stderr or 'install.ps1 is for Windows' in result.stderr
    assert not prefix.exists()


@pytest.fixture
def ps_world(tmp_path):
    releases = Releases(tmp_path)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_INSTALL_CHANNEL_URL=str(releases.channel), DEWY_INSTALL_DOWNLOAD_URL=str(releases.root))
    return releases, env, tmp_path / 'dewy home'


def cmd(prefix: Path, *args, env, check=True, cwd=None):
    result = subprocess.run([str(prefix / 'bin' / 'dewy.cmd'), *args], env=env, capture_output=True,
                            text=True, timeout=300, check=False, cwd=cwd)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


@windows_only
@pytest.mark.parametrize('shell', POWERSHELLS)
def test_powershell_install_update_and_rollback(ps_world, real_toolchain, shell, tmp_path):
    releases, env, prefix = ps_world
    a = releases.publish('real a', archive=real_archive(real_toolchain))
    releases.point(a)
    out = powershell(shell, '-Prefix', str(prefix), '-NoModifyPath', env=env).stdout
    assert f'Installed Dewy toolchain {a}' in out
    assert pointer(prefix) == [a, '']
    work = tmp_path / 'my project'
    work.mkdir()
    (work / 'main.dewy').write_text(SAMPLE)
    cmd(prefix, 'build', 'main.dewy', '-o', 'main.exe', env=env, cwd=work)
    assert subprocess.run([str(work / 'main.exe')], cwd=work).returncode == 42
    assert cmd(prefix, '--print-lib', env=env).stdout.strip().lower() == str(prefix / 'toolchains' / a / 'lib').lower()
    assert cmd(prefix, 'check', 'missing file.dewy', env=env, check=False).returncode != 0

    b = releases.publish('real b', archive=real_archive(real_toolchain))
    releases.point(b)
    cmd(prefix, 'update', env=env)
    assert pointer(prefix) == [b, a]
    cmd(prefix, 'rollback', env=env)
    assert pointer(prefix) == [a, b]
    c = releases.publish('real c', archive=real_archive(real_toolchain))
    cmd(prefix, 'update', '--release', c, env=env)
    assert pointer(prefix) == [c, a]
    assert toolchains(prefix) == sorted([a, c])


@windows_only
@pytest.mark.parametrize('defect', ['checksum', 'traversal', 'symlink', 'wrong-platform'])
def test_powershell_rejects_defective_release(ps_world, real_toolchain, defect):
    releases, env, prefix = ps_world
    shell = POWERSHELLS[0]
    a = releases.publish('real a', archive=real_archive(real_toolchain))
    releases.point(a)
    powershell(shell, '-Prefix', str(prefix), '-NoModifyPath', env=env)
    before = snapshot(prefix)
    b = releases.publish('b', defect='' if defect == 'checksum' else defect)
    releases.point(b)
    if defect == 'checksum':
        fake_archive(releases.root / b / f'dewy-core-{HOST}.tar.gz', HOST, revision_for('b'), 'tampered')
    result = powershell(shell, '-Prefix', str(prefix), '-NoModifyPath', env=env, check=False)
    assert result.returncode != 0
    assert {k: v for k, v in snapshot(prefix).items() if not k.endswith('.lock')} == \
        {k: v for k, v in before.items() if not k.endswith('.lock')}
    assert pointer(prefix) == [a, '']


@windows_only
def test_powershell_interrupted_download(ps_world, real_toolchain):
    releases, env, prefix = ps_world
    shell = POWERSHELLS[0]
    server = Server(releases.root.parent)
    try:
        env = dict(env, DEWY_INSTALL_CHANNEL_URL=f'{server.url}/toolchain-channel.txt',
                   DEWY_INSTALL_DOWNLOAD_URL=f'{server.url}/served')
        a = releases.publish('real a', archive=real_archive(real_toolchain))
        releases.point(a)
        powershell(shell, '-Prefix', str(prefix), '-NoModifyPath', env=env)
        b = releases.publish('real b', archive=real_archive(real_toolchain))
        releases.point(b)
        server.stall.add(f'dewy-core-{HOST}.tar.gz')
        process = subprocess.Popen([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                    str(ROOT / 'install.ps1'), '-Prefix', str(prefix), '-NoModifyPath'],
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert server.stalled.wait(120)
        process.kill()
        process.wait(30)
        assert pointer(prefix) == [a, '']
        assert cmd(prefix, '--version', env=env).stdout.startswith('dewy-core ')
        server.stall.clear()
        powershell(shell, '-Prefix', str(prefix), '-NoModifyPath', env=env)
        assert pointer(prefix) == [b, a]
    finally:
        server.close()
