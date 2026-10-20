"""Assemble a toolchain release from the packages of a certified CI run.

    python3 -m tools.compiler.release tag SHA
    python3 -m tools.compiler.release certify SHA                    # prints the CI run id
    python3 -m tools.compiler.release assemble SHA ARTIFACTS DIST    # ARTIFACTS/<platform>/dewy-core-<platform>.tar.gz
    python3 -m tools.compiler.release notes SHA RUN_ID
    python3 -m tools.compiler.release compare DIST DOWNLOADED        # the draft holds exactly DIST

`.github/workflows/release.yml` runs these; see docs/DEVELOPMENT.md. Tags
are `dewy-<language version>-dev.<commit date, UTC>.<12-digit commit>`, so
one commit always maps to the same immutable tag.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from tools.compiler.channel import ARCHIVES, ASSETS, INSTALLERS, PLATFORMS, REPO, TAG
from tools.compiler.package import HOSTS, PLATFORMS as HOST_PLATFORMS

ROOT = Path(__file__).resolve().parents[2]
HOST_FOR = {platform: host for host, platform in HOST_PLATFORMS.items()}
SHA = re.compile(r'[0-9a-f]{40}')
# CI jobs that must all have succeeded for the certified commit.
REQUIRED_JOBS = ('bootstrap-and-test', 'compile-speed')
SMOKE_HOSTS = ('windows-x86_64', 'macos-arm64', 'linux-arm64')


class ReleaseError(ValueError):
    pass


def git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True, text=True,
                          env=dict(os.environ, TZ='UTC')).stdout


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_sha(sha: str) -> str:
    if not SHA.fullmatch(sha):
        raise ReleaseError(f'expected a full 40-digit lowercase commit SHA, got {sha!r}')
    return sha


def version_at(sha: str) -> str:
    return git('show', f'{sha}:VERSION').strip()


def tag_for(sha: str) -> str:
    check_sha(sha)
    date = git('show', '-s', '--format=%cd', '--date=format-local:%Y%m%d', sha).strip()
    core = version_at(sha).split('-')[0]
    tag = f'dewy-{core}-dev.{date}.{sha[:12]}'
    if not TAG.fullmatch(tag):
        raise ReleaseError(f'unexpected tag {tag!r}')
    return tag


def certified_run(sha: str, runs: list[dict], jobs: dict[int, list[dict]],
                  artifacts: dict[int, list[dict]]) -> int:
    """The newest successful push run of CI for `sha` whose every job passed."""
    problems = []
    candidates = [run for run in runs if run.get('head_sha') == sha and run.get('event') == 'push'
                  and run.get('conclusion') == 'success' and run.get('path', '').endswith('ci.yml')]
    for run in sorted(candidates, key=lambda run: run['run_number'], reverse=True):
        names = {job['name']: job['conclusion'] for job in jobs.get(run['id'], [])}
        failed = sorted(name for name, conclusion in names.items() if conclusion != 'success')
        missing = [name for name in REQUIRED_JOBS if names.get(name) != 'success']
        missing += [f'host-smoke {host}' for host in SMOKE_HOSTS
                    if not any(name.startswith('host-smoke') and host in name for name in names)]
        present = {a['name'] for a in artifacts.get(run['id'], []) if not a.get('expired')}
        missing += [f'artifact dewy-core-{p}-{sha}' for p in PLATFORMS if f'dewy-core-{p}-{sha}' not in present]
        if failed or missing:
            problems.append(f'run {run["id"]}: ' + ', '.join([*(f'{n} did not succeed' for n in failed),
                                                              *(f'{n} missing' for n in missing)]))
            continue
        return run['id']
    detail = '; '.join(problems) or 'no successful CI push run'
    raise ReleaseError(f'{sha} is not certified: {detail}')


def gh_api(path: str) -> dict:
    result = subprocess.run(['gh', 'api', '-H', 'Accept: application/vnd.github+json', path],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise ReleaseError(f'gh api {path}: {result.stderr.strip()}')
    return json.loads(result.stdout)


def certify(sha: str, repo: str = REPO) -> int:
    check_sha(sha)
    runs = gh_api(f'repos/{repo}/actions/workflows/ci.yml/runs?head_sha={sha}&per_page=100')['workflow_runs']
    jobs, artifacts = {}, {}
    for run in runs:
        if run.get('conclusion') == 'success' and run.get('event') == 'push':
            jobs[run['id']] = gh_api(f'repos/{repo}/actions/runs/{run["id"]}/jobs?per_page=100')['jobs']
            artifacts[run['id']] = gh_api(f'repos/{repo}/actions/runs/{run["id"]}/artifacts?per_page=100')['artifacts']
    return certified_run(sha, runs, jobs, artifacts)


def check_archive(path: Path, sha: str, platform: str, version: str) -> None:
    """The CI package for `platform`, built from `sha`, exactly as package.py wrote it."""
    name = path.name
    sidecar = path.with_name(name + '.sha256')
    data = path.read_bytes()
    if not sidecar.is_file() or sidecar.read_text() != f'{digest(data)}  {name}\n':
        raise ReleaseError(f'{name}: missing or mismatched .sha256 sidecar')
    host = HOST_FOR[platform]
    binary = f'bin/{HOSTS[host][1]}'
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive.getmembers():
            parts = member.name.split('/')
            if parts[0] != 'dewy-core' or len(parts) < 2 or any(p in ('', '.', '..') for p in parts[1:]):
                raise ReleaseError(f'{name}: unexpected member {member.name!r}')
            if not member.isfile():
                raise ReleaseError(f'{name}: {member.name} is not a regular file')
            files[member.name[len('dewy-core/'):]] = (archive.extractfile(member).read(), member.mode)
    if 'PACKAGE.json' not in files or 'RELEASE' not in files:
        raise ReleaseError(f'{name}: no PACKAGE.json or RELEASE')
    metadata = json.loads(files.pop('PACKAGE.json')[0])
    if metadata.get('format') != 1 or metadata.get('host') != host:
        raise ReleaseError(f'{name}: PACKAGE.json is not a {host} package')
    if metadata.get('revision') != sha:
        raise ReleaseError(f'{name}: PACKAGE.json revision {metadata.get("revision")} is not {sha}')
    if set(metadata['files']) != set(files):
        raise ReleaseError(f'{name}: payload differs from PACKAGE.json')
    for member, (content, _) in files.items():
        if digest(content) != metadata['files'][member]:
            raise ReleaseError(f'{name}: {member} does not match PACKAGE.json')
    release = f'dewy-toolchain-release 1\nversion {version}\nplatform {platform}\nrevision {sha}\n'
    if files['RELEASE'][0].decode() != release:
        raise ReleaseError(f'{name}: RELEASE does not identify {platform} {sha} (version {version})')
    if binary not in files or not files[binary][1] & 0o100 or 'lib/core/rt.jo' not in files:
        raise ReleaseError(f'{name}: no executable {binary} or standard library')


def assemble(sha: str, artifacts: Path, dist: Path, installers: Path | None = None) -> list[Path]:
    """Verify the four CI packages and lay out every release asset in `dist`.

    The installers come from `sha` itself unless `installers` names a directory.
    """
    check_sha(sha)
    version = version_at(sha)
    dist.mkdir(parents=True, exist_ok=False)
    for platform, name in zip(PLATFORMS, ARCHIVES):
        source = artifacts / platform / name
        if not source.is_file():
            raise ReleaseError(f'{source} is missing')
        check_archive(source, sha, platform, version)
        shutil.copyfile(source, dist / name)
        shutil.copyfile(source.with_name(name + '.sha256'), dist / f'{name}.sha256')
    for name in INSTALLERS:
        if installers is not None:
            content = (installers / name).read_bytes()
        else:
            content = subprocess.run(['git', 'show', f'{sha}:{name}'], cwd=ROOT, check=True,
                                     capture_output=True).stdout
        (dist / name).write_bytes(content)
    sums = ''.join(f'{digest((dist / name).read_bytes())}  {name}\n' for name in ASSETS)
    (dist / 'SHA256SUMS').write_text(sums, newline='\n')
    return sorted(dist.iterdir())


def notes(sha: str, run_id: str, repo: str = REPO) -> str:
    tag = tag_for(sha)
    base = f'https://github.com/{repo}/releases/download/{tag}'
    return f"""Development toolchain of the current Dewy compiler (language version {version_at(sha)}), \
built from {sha} and certified by CI run https://github.com/{repo}/actions/runs/{run_id}.

Linux x86_64/aarch64 and macOS arm64:

    curl -fsSL {base}/install.sh | bash -s -- --release {tag}

Windows x86_64 (PowerShell):

    & ([scriptblock]::Create((irm {base}/install.ps1))) -Release {tag}

The installers verify each download against this release's SHA256SUMS, keep the previous
toolchain for `dewy rollback`, and leave earlier installations in ~/.dewy untouched.
Each `dewy-core-<platform>.tar.gz` holds `bin/`, `lib/`, `RELEASE` and `PACKAGE.json`
(payload hashes) and runs after extraction without Python or a C compiler.
"""


def compare(dist: Path, downloaded: Path) -> None:
    expected = {p.name: digest(p.read_bytes()) for p in dist.iterdir()}
    actual = {p.name: digest(p.read_bytes()) for p in downloaded.iterdir()}
    if expected != actual:
        differ = sorted(set(expected) ^ set(actual) | {n for n in expected if actual.get(n) != expected[n]})
        raise ReleaseError(f'the draft release differs from the assembled assets: {", ".join(differ)}')


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = cli.add_subparsers(dest='command', required=True)
    commands.add_parser('tag').add_argument('sha')
    certify_cli = commands.add_parser('certify')
    certify_cli.add_argument('sha')
    certify_cli.add_argument('--repo', default=REPO)
    assemble_cli = commands.add_parser('assemble')
    for name in ('sha', 'artifacts', 'dist'):
        assemble_cli.add_argument(name)
    notes_cli = commands.add_parser('notes')
    notes_cli.add_argument('sha')
    notes_cli.add_argument('run_id')
    notes_cli.add_argument('--repo', default=REPO)
    compare_cli = commands.add_parser('compare')
    compare_cli.add_argument('dist', type=Path)
    compare_cli.add_argument('downloaded', type=Path)
    args = cli.parse_args(argv)
    try:
        if args.command == 'tag':
            print(tag_for(args.sha))
        elif args.command == 'certify':
            print(certify(args.sha, args.repo))
        elif args.command == 'assemble':
            for path in assemble(args.sha, Path(args.artifacts), Path(args.dist)):
                print(path)
        elif args.command == 'notes':
            sys.stdout.write(notes(args.sha, args.run_id, args.repo))
        else:
            compare(args.dist, args.downloaded)
    except (ReleaseError, subprocess.CalledProcessError, OSError, KeyError, json.JSONDecodeError,
            tarfile.TarError) as error:
        print(f'release: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
