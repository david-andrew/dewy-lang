"""Recreate the historical bootstrap capsule from Git, or verify and build its G2 offline."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / 'bootstrap-seed'
ARCHIVE = 'source.tar.xz'
INVENTORY = 'members.json'
RECIPE = 'build-g2.sh'
G2 = 'dewy-core-bootstrap'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate(repo: Path, revision: str, dest: Path) -> None:
    """Read only objects at the named commit. Never consult working-tree twins."""
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', revision + '^{commit}'],
                                     cwd=repo, text=True).strip()
    # G1 also loads Jo runtime modules from lib/std and lib/game. The case table
    # is the one binary data file embedded while compiling these sources.
    inputs = ['compiler', 'lib', 'stage0', 'bootstrap', 'LICENSE']
    tree = subprocess.check_output(['git', 'archive', '--format=tar', commit, *inputs], cwd=repo)
    files = {}
    twins = {}
    with tarfile.open(fileobj=io.BytesIO(tree)) as source:
        for member in source:
            if not member.isfile():
                continue
            path = PurePosixPath(member.name)
            if path.parent == PurePosixPath('compiler') and path.suffix == '.dewy':
                twins[path.name.encode()] = path.with_suffix('.jo').name.encode()
            elif (member.name in ('LICENSE', 'lib/std/unicode/case_mapping.bin')
                  or path.parent.name == 'stage0' or path.suffix == '.jo'):
                files[member.name] = source.extractfile(member).read()
    for twin in twins.values():
        if 'compiler/' + twin.decode() not in files:
            raise ValueError(f'missing frozen twin {twin.decode()}')
    use = re.compile(rb"^use '([^'\n]+\.dewy)'\n", re.MULTILINE)
    for name, data in files.items():
        if name.startswith(('compiler/', 'bootstrap/')):
            files[name] = use.sub(lambda m: b"use '" + twins[m[1]] + b"'\n", data)
    dest.mkdir(exist_ok=True, parents=True)
    members = {}
    with tarfile.open(dest / ARCHIVE, 'w:xz', format=tarfile.USTAR_FORMAT, preset=6) as archive:
        for name, data in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(data))
            members[name] = sha(data)
    (dest / INVENTORY).write_bytes((json.dumps(members, indent=2) + '\n').encode('ascii'))


def checked(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    if sha(data) != expected:
        raise RuntimeError(f'SHA-256 mismatch for {path}')
    return data


def extract(data: bytes, members: dict[str, str], dest: Path) -> None:
    """Accept only the exact ordered list of regular files and contents in the pin."""
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:xz') as archive:
        for entry, name in zip(archive, sorted(members), strict=True):
            path = PurePosixPath(name)
            if (entry.name != name or not entry.isfile() or path.is_absolute()
                    or '..' in path.parts or path.as_posix() != name):
                raise ValueError(f'unexpected archive member {entry.name}')
            content = archive.extractfile(entry).read()
            if sha(content) != members[name]:
                raise RuntimeError(f'SHA-256 mismatch for archive member {name}')
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


def obtain(cache: Path, pin_dir: Path = PIN, *, log: Path | None = None) -> tuple[Path, dict]:
    """Verify the pin even on a cache hit. Publish only a freshly verified G2."""
    pin = json.loads((pin_dir / 'pin.json').read_bytes())
    host = f'{platform.system().lower()}-{platform.machine()}'
    if host != pin['host']:
        raise RuntimeError(f'the pinned G2 requires {pin["host"]}, running on {host}')
    recipe = checked(pin_dir / RECIPE, pin['recipe_sha256'])
    archive = checked(pin_dir / ARCHIVE, pin['archive_sha256'])
    members = json.loads(checked(pin_dir / INVENTORY, pin['members_sha256']))
    directory = cache / host / pin['recipe_sha256'] / pin['archive_sha256']
    binary = directory / G2
    provenance = {k: pin[k] for k in ('revision', 'recipe_version', 'recipe_sha256',
                                      'archive_sha256', 'members_sha256', 'host', 'g2_sha256')}
    if binary.is_symlink():
        raise RuntimeError(f'expected a regular cached G2 at {binary}')
    if binary.exists():
        if not binary.is_file():
            raise RuntimeError(f'expected a regular cached G2 at {binary}')
        checked(binary, pin['g2_sha256'])
        if not os.access(binary, os.X_OK):
            raise RuntimeError(f'cached G2 is not executable: {binary}')
        return binary, {**provenance, 'cache_hit': True}
    directory.mkdir(exist_ok=True, parents=True)
    with tempfile.TemporaryDirectory(prefix='build-', dir=directory) as temp:
        work = Path(temp)
        extract(archive, members, work)
        (work / RECIPE).write_bytes(recipe)
        # No inherited compiler flags, make options, library or Dewy cache.
        env = {'PATH': os.defpath, 'TMPDIR': str(work.resolve()), 'LC_ALL': 'C'}
        command = ['sh', RECIPE]
        started = time.perf_counter()
        result = subprocess.run(command, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, check=False)
        if log is not None:
            log.write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(f'{RECIPE} failed with status {result.returncode}:\n{result.stdout}')
        provenance['build_step'] = {'command': command, 'wall_seconds': time.perf_counter() - started,
                                    'returncode': result.returncode}
        rebuilt = work / 'bin' / G2
        checked(rebuilt, pin['g2_sha256'])
        built = {name: sha((work / name).read_bytes()) for name in ('stage0/sloppy0', 'bin/core-bootstrap')}
        built['bin/' + G2] = pin['g2_sha256']
        rebuilt.replace(binary)
    return binary, {**provenance, 'cache_hit': False, 'built_sha256': built}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest='command', required=True)
    gen = commands.add_parser('generate', help='recreate source.tar.xz and members.json from Git')
    gen.add_argument('revision')
    gen.add_argument('dest', type=Path)
    gen.add_argument('--repo', type=Path, default=ROOT)
    build = commands.add_parser('build', help='obtain the pinned, SHA-256-verified native G2')
    build.add_argument('cache', type=Path)
    args = cli.parse_args()
    if args.command == 'generate':
        generate(args.repo, args.revision, args.dest)
    else:
        print(obtain(args.cache)[0])
