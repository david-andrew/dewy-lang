"""Write the toolchain channel pointer (toolchain-channel.txt) for a published release.

    python3 -m tools.compiler.channel --tag dewy-0.0.0-dev.20261020.0123456789ab --output site/dist/toolchain-channel.txt
    python3 -m tools.compiler.channel --latest --output site/dist/toolchain-channel.txt

The pointer names one published release and the SHA-256 of each asset an
installer may download. Format version 1, ASCII, LF line endings, at most
64 lines; anything else is invalid:

    dewy-toolchain-channel 1
    release <tag>
    sha256 <64 lowercase hex> <asset>      (one or more lines)
    end

Installers read it line by line and never evaluate it. The digests come from
the release's SHA256SUMS and must agree with GitHub's own asset digests; the
release must be published and carry every platform archive and installer.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = 'david-andrew/dewy-lang'
PLATFORMS = ('linux-x86_64', 'linux-arm64', 'macos-arm64', 'windows-x86_64')
ARCHIVES = tuple(f'dewy-core-{platform}.tar.gz' for platform in PLATFORMS)
INSTALLERS = ('install.sh', 'install.ps1')
ASSETS = ARCHIVES + INSTALLERS
HEADER = 'dewy-toolchain-channel 1'
TAG = re.compile(r'dewy-[0-9]+\.[0-9]+\.[0-9]+-dev\.[0-9]{8}\.[0-9a-f]{12}')
ASSET = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*')
SHA256 = re.compile(r'[0-9a-f]{64}')
MAX_LINES = 64


class ChannelError(ValueError):
    pass


def parse_sums(text: str) -> dict[str, str]:
    """Parse sha256sum output (`<hex>  <name>` lines), rejecting anything else."""
    sums = {}
    for line in text.splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)', line)
        if not match or match[2] in sums:
            raise ChannelError(f'malformed SHA256SUMS line: {line!r}')
        sums[match[2]] = match[1]
    return sums


def render(tag: str, sums: dict[str, str]) -> str:
    if not TAG.fullmatch(tag):
        raise ChannelError(f'not a toolchain release tag: {tag!r}')
    missing = [name for name in ASSETS if name not in sums]
    if missing:
        raise ChannelError(f'{tag} lacks {", ".join(missing)}')
    lines = [HEADER, f'release {tag}']
    lines += [f'sha256 {sums[name]} {name}' for name in ASSETS]
    lines.append('end')
    text = '\n'.join(lines) + '\n'
    parse(text)
    return text


def parse(text: str) -> tuple[str, dict[str, str]]:
    """The reference parser; install.sh and install.ps1 implement the same rules."""
    if not text.isascii() or '\r' in text or not text.endswith('\n'):
        raise ChannelError('channel must be ASCII with LF line endings')
    lines = text[:-1].split('\n')
    if len(lines) > MAX_LINES or len(lines) < 4:
        raise ChannelError('channel has the wrong number of lines')
    if lines[0] != HEADER:
        raise ChannelError(f'unsupported channel header: {lines[0]!r}')
    if not lines[1].startswith('release ') or not TAG.fullmatch(lines[1][8:]):
        raise ChannelError(f'malformed release line: {lines[1]!r}')
    if lines[-1] != 'end':
        raise ChannelError('channel is truncated (no end line)')
    sums = {}
    for line in lines[2:-1]:
        fields = line.split(' ')
        if (len(fields) != 3 or fields[0] != 'sha256' or not SHA256.fullmatch(fields[1])
                or not ASSET.fullmatch(fields[2]) or fields[2] in sums):
            raise ChannelError(f'malformed channel line: {line!r}')
        sums[fields[2]] = fields[1]
    return lines[1][8:], sums


def fetch(url: str, *, api: bool = False) -> bytes:
    headers = {'User-Agent': 'dewy-channel'}
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if api:
        headers['Accept'] = 'application/vnd.github+json'
        if token:
            headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        return response.read()


def published(repo: str, tag: str | None) -> dict:
    """The published (non-draft) release for `tag`, or the newest toolchain release."""
    if tag is not None:
        if not TAG.fullmatch(tag):
            raise ChannelError(f'not a toolchain release tag: {tag!r}')
        try:
            release = json.loads(fetch(f'https://api.github.com/repos/{repo}/releases/tags/{tag}', api=True))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise ChannelError(f'{tag} is not a published release of {repo}') from error
            raise
    else:
        releases = json.loads(fetch(f'https://api.github.com/repos/{repo}/releases?per_page=100', api=True))
        candidates = [r for r in releases if not r['draft'] and TAG.fullmatch(r['tag_name'])]
        if not candidates:
            raise ChannelError(f'{repo} has no published toolchain release')
        release = max(candidates, key=lambda r: r['published_at'])
    if release.get('draft') or release['tag_name'] != (tag or release['tag_name']):
        raise ChannelError(f'{release["tag_name"]} is not published')
    return release


def channel_for(repo: str, tag: str | None, sums_text: str | None = None) -> str:
    release = None
    if sums_text is None:
        release = published(repo, tag)
        tag = release['tag_name']
        sums_text = fetch(f'https://github.com/{repo}/releases/download/{tag}/SHA256SUMS').decode()
    sums = parse_sums(sums_text)
    if release is not None:
        assets = {asset['name']: asset for asset in release['assets']}
        for name in ASSETS:
            if name not in assets:
                raise ChannelError(f'{tag} has no {name} asset')
            reported = assets[name].get('digest')
            if reported and reported != f'sha256:{sums.get(name)}':
                raise ChannelError(f'{tag}: SHA256SUMS disagrees with GitHub for {name}')
    return render(tag, sums)


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    which = cli.add_mutually_exclusive_group(required=True)
    which.add_argument('--tag', help='published release tag')
    which.add_argument('--latest', action='store_true', help='the newest published toolchain release')
    cli.add_argument('--sums', type=Path, help='use this SHA256SUMS instead of downloading it (requires --tag)')
    cli.add_argument('--repo', default=REPO)
    cli.add_argument('--output', type=Path, help='write here instead of stdout')
    args = cli.parse_args(argv)
    if args.sums and not args.tag:
        cli.error('--sums requires --tag')
    try:
        text = channel_for(args.repo, args.tag, args.sums.read_text() if args.sums else None)
    except (ChannelError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f'channel: {error}', file=sys.stderr)
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, newline='\n')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
