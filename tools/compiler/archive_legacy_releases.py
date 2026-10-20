"""Label the legacy native-*/udewy-* releases "Archived implementation".

    python3 -m tools.compiler.archive_legacy_releases            # print the plan (no changes)
    python3 -m tools.compiler.archive_legacy_releases --verbose  # ...listing every release
    python3 -m tools.compiler.archive_legacy_releases --apply    # carry it out with gh

Every tag, release and asset stays. Each title gains the prefix
"Archived implementation: " and each body a leading note. The newest complete
native-* release is marked Latest: the cached legacy installers download
releases/latest/download/{dewy-linux-x86_64.tar.gz,udewy-linux-x86_64}, so
that release must carry both, matching their sidecars and the archive's own
SHA256SUMS. New toolchain releases are prereleases and never become Latest.
The old "Release native Dewy" workflow, which still runs from master until the
cutover, is disabled. Running the script again changes nothing more.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import urllib.request

REPO = 'david-andrew/dewy-lang'
LEGACY = re.compile(r'(native|udewy)-[0-9a-f]+')
PREFIX = 'Archived implementation: '
NOTE = ('**Archived implementation.** This release belongs to the retired native Dewy/µDewy '
        'implementation (branch archive/master-pre-restart). It stays available so existing '
        'installations and pinned downloads keep working. Current toolchains are published as '
        '`dewy-0.0.0-dev.*` prereleases; see https://dewy-lang.org/install/.\n\n')
ARCHIVE, UDEWY = 'dewy-linux-x86_64.tar.gz', 'udewy-linux-x86_64'
LEGACY_ASSETS = (ARCHIVE, f'{ARCHIVE}.sha256', UDEWY, f'{UDEWY}.sha256')
# What the legacy install.sh requires inside the archive before it switches.
ARCHIVE_MEMBERS = ('dewy', 'udewy', 'VERSION', 'SHA256SUMS', 'library/path.dewy',
                   'library/unicode/grapheme_break.bin', 'tools/dewy_gdb.py', 'tools/dewy_lldb.py')
OLD_WORKFLOW = '.github/workflows/release-native.yml'


def gh(*args: str, input: str | None = None) -> str:
    result = subprocess.run(['gh', *args], capture_output=True, text=True, input=input, check=False)
    if result.returncode:
        raise RuntimeError(f'gh {" ".join(args)}: {result.stderr.strip()}')
    return result.stdout


def gh_json(path: str):
    return json.loads(gh('api', '-H', 'Accept: application/vnd.github+json', path))


def releases(repo: str) -> list[dict]:
    pages = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100'))
    return [release for page in pages for release in page]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': 'dewy-archive-legacy'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_complete(release: dict) -> list[str]:
    """Problems that would break the cached legacy installers; empty when complete."""
    assets = {asset['name']: asset for asset in release['assets']}
    missing = [name for name in LEGACY_ASSETS if name not in assets]
    if missing:
        return [f'missing {", ".join(missing)}']
    problems = []
    for name in (ARCHIVE, UDEWY):
        sidecar = fetch(assets[f'{name}.sha256']['browser_download_url']).decode()
        if sidecar.split()[:1] != [assets[name]['digest'].removeprefix('sha256:')]:
            problems.append(f'{name}.sha256 does not match GitHub\'s digest')
    archive = fetch(assets[ARCHIVE]['browser_download_url'])
    if f'sha256:{sha256(archive)}' != assets[ARCHIVE]['digest']:
        problems.append(f'{ARCHIVE} download does not match its digest')
    # Read the archive in memory only; it is never extracted.
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as contents:
        files = {m.name.removeprefix('./'): m for m in contents.getmembers() if m.isfile()}
        absent = [name for name in ARCHIVE_MEMBERS if name not in files]
        if absent:
            return problems + [f'{ARCHIVE} lacks {", ".join(absent)}']
        for line in contents.extractfile(files['SHA256SUMS']).read().decode().splitlines():
            expected, name = line.split(maxsplit=1)
            name = name.lstrip('*').removeprefix('./')
            if name not in files or sha256(contents.extractfile(files[name]).read()) != expected:
                problems.append(f'{ARCHIVE}: {name} fails its SHA256SUMS')
    return problems


def plan(repo: str) -> dict:
    legacy = [r for r in releases(repo) if LEGACY.fullmatch(r['tag_name']) and not r['draft']]
    legacy.sort(key=lambda r: r['published_at'], reverse=True)
    try:
        latest = gh_json(f'repos/{repo}/releases/latest')['tag_name']
    except RuntimeError:
        latest = None
    chosen, rejected = None, []
    for release in legacy:
        if not release['tag_name'].startswith('native-'):
            continue
        problems = check_complete(release)
        if not problems:
            chosen = release
            break
        rejected.append((release['tag_name'], problems))
    edits = []
    for release in legacy:
        title = release['name'] or release['tag_name']
        body = release['body'] or ''
        edits.append({'tag': release['tag_name'],
                      'title': title if title.startswith(PREFIX) else PREFIX + title,
                      'body': body if body.startswith(NOTE) else NOTE + body,
                      'changed': not title.startswith(PREFIX) or not body.startswith(NOTE)})
    workflows = gh_json(f'repos/{repo}/actions/workflows?per_page=100')['workflows']
    old = next((w for w in workflows if w['path'] == OLD_WORKFLOW), None)
    return {'legacy': legacy, 'latest': latest, 'chosen': chosen, 'rejected': rejected,
            'edits': edits, 'workflow': old}


def describe(steps: dict, repo: str, verbose: bool) -> None:
    legacy, chosen = steps['legacy'], steps['chosen']
    kinds = {kind: sum(r['tag_name'].startswith(kind) for r in legacy) for kind in ('native-', 'udewy-')}
    print(f'{repo}: {len(legacy)} legacy releases ({kinds["native-"]} native-*, {kinds["udewy-"]} udewy-*); '
          f'tags and assets are kept.')
    print(f'Current Latest release: {steps["latest"] or "none"}')
    for tag, problems in steps['rejected']:
        print(f'  skipped {tag} as Latest: {"; ".join(problems)}')
    if chosen is None:
        print('No complete native-* release found; Latest would not be set.')
    else:
        same = 'already Latest' if chosen['tag_name'] == steps['latest'] else 'will become Latest'
        print(f'Latest legacy release: {chosen["tag_name"]} ({chosen["published_at"]}), {same}; '
              f'its {", ".join(LEGACY_ASSETS)} match their sidecars and the archive passes its SHA256SUMS.')
    changed = [e for e in steps['edits'] if e['changed']]
    print(f'Relabel {len(changed)} of {len(steps["edits"])} releases '
          f'(title prefix "{PREFIX.strip()}", body note):')
    shown = changed if verbose else changed[:3] + changed[-2:] if len(changed) > 5 else changed
    for edit in shown:
        print(f'  {edit["tag"]}: "{edit["title"]}"')
    if len(shown) < len(changed):
        print(f'  ... and {len(changed) - len(shown)} more (--verbose lists them)')
    workflow = steps['workflow']
    if workflow is None:
        print(f'Workflow {OLD_WORKFLOW}: not registered')
    else:
        action = 'will be disabled' if workflow['state'] == 'active' else 'already disabled'
        print(f'Workflow "{workflow["name"]}" ({OLD_WORKFLOW}) is {workflow["state"]}; {action}.')
    print('Commands, in order:')
    if workflow is not None and workflow['state'] == 'active':
        print(f'  gh workflow disable {workflow["id"]}')
    others = [e for e in changed if chosen is None or e['tag'] != chosen['tag_name']]
    for edit in others if verbose else others[:1]:
        print(f'  gh release edit {edit["tag"]} --title ... --notes-file ... --latest=false')
    if not verbose and len(others) > 1:
        print(f'  ... ({len(others) - 1} more like it)')
    if chosen is not None:
        print(f'  gh release edit {chosen["tag_name"]} --title ... --notes-file ... --latest')


def apply(steps: dict, repo: str) -> None:
    chosen = steps['chosen']
    if chosen is None:
        raise RuntimeError('no complete legacy release to keep as Latest; nothing applied')
    workflow = steps['workflow']
    if workflow is not None and workflow['state'] == 'active':
        gh('workflow', 'disable', str(workflow['id']), '-R', repo)
        print(f'disabled {OLD_WORKFLOW}')
    # The release kept as Latest goes last, followed by a check.
    ordered = sorted(steps['edits'], key=lambda edit: edit['tag'] == chosen['tag_name'])
    for edit in ordered:
        is_chosen = edit['tag'] == chosen['tag_name']
        if not edit['changed'] and not is_chosen:
            continue
        gh('release', 'edit', edit['tag'], '-R', repo, '--title', edit['title'], '--notes-file', '-',
           '--latest' if is_chosen else '--latest=false', input=edit['body'])
        print(f'archived {edit["tag"]}' + (' (Latest)' if is_chosen else ''))
    latest = gh_json(f'repos/{repo}/releases/latest')['tag_name']
    if latest != chosen['tag_name']:
        raise RuntimeError(f'Latest is {latest}, expected {chosen["tag_name"]}')
    print(f'Latest is {latest}')


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--apply', action='store_true', help='carry out the plan (default: print it)')
    cli.add_argument('--verbose', action='store_true', help='list every release and command')
    cli.add_argument('--repo', default=REPO)
    args = cli.parse_args(argv)
    try:
        steps = plan(args.repo)
        describe(steps, args.repo, args.verbose)
        if args.apply:
            apply(steps, args.repo)
        else:
            print('Dry run: nothing was changed. Run again with --apply to carry it out.')
    except (RuntimeError, OSError, ValueError, tarfile.TarError) as error:
        print(f'archive_legacy_releases: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
