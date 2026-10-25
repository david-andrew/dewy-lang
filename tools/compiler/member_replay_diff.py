"""Compare members-loop replay with per-member checking: diagnostics and output bytes.

The same compiler, source path, output path, and library are used in both modes.
The corpus includes golden cases, examples, and both core and design ladder
programs (including 99_dewy_frontend's imported tokens.dewy). Matching rejections
count only when exit status and the complete ordered diagnostics match.

    python3 -m tools.compiler.member_replay_diff --modes native release g wasm32 aarch64-mac x86_64-windows
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MODES = {'native': [], 'release': ['--release'], 'g': ['-g'],
         'wasm32': ['--target', 'wasm32'], 'aarch64-mac': ['--target', 'aarch64-mac'],
         'x86_64-windows': ['--target', 'x86_64-windows']}


def programs() -> list[Path]:
    return sorted(set([*(ROOT / 'tests/cases').rglob('*.dewy'),
                       *(ROOT / 'examples').glob('*.dewy'),
                       *(ROOT / 'tests/ladder').glob('*/core.dewy'),
                       *(ROOT / 'tests/ladder').glob('*/design.dewy')]))


def compare(compiler: Path, source: Path, mode: str, directory: Path) -> tuple[bool, bool]:
    """(identical, accepted by reference). Keep both diagnostics on a difference."""
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / 'out'
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(DEWY_CORE_LIB=str(ROOT / 'lib'), DEWY_EMIT_WORKERS='1')
    results = []
    for selection in ('reference', 'shared'):
        shutil.rmtree(output, ignore_errors=True)
        output.mkdir()
        run = subprocess.run([compiler, 'build', source, '-o', output / 'program', *MODES[mode]],
                             cwd=ROOT, env=env | {'DEWY_MEMBERS': selection},
                             capture_output=True, timeout=180, check=False)
        files = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in output.rglob('*') if p.is_file()}
        results.append((run.returncode, run.stdout, run.stderr, files))
    identical = results[0] == results[1]
    if identical:
        shutil.rmtree(directory)
    else:
        (directory / 'source.txt').write_text(f'{source}\n{mode}\n')
        for selection, (status, stdout, stderr, files) in zip(('reference', 'shared'), results):
            (directory / f'{selection}.stdout').write_bytes(stdout)
            (directory / f'{selection}.stderr').write_bytes(stderr)
            (directory / f'{selection}.files').write_text(f'exit {status}\n' + '\n'.join(
                f'{digest} {name}' for name, digest in sorted(files.items())) + '\n')
    return identical, results[0][0] == 0


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--compiler', type=Path)
    cli.add_argument('--modes', nargs='+', choices=MODES, default=['native'])
    cli.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    cli.add_argument('-k', default='', help='only source paths containing this text')
    cli.add_argument('--scratch', type=Path, default=Path.home() / 'dev/tmp/member-replay-diff')
    args = cli.parse_args(argv)
    if args.compiler is None:
        from tools.core import toolchain
        compiler = toolchain()
    else:
        compiler = args.compiler.resolve(strict=True)
    args.scratch.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='run-', dir=args.scratch))
    sources = [p for p in programs() if args.k in str(p)]
    jobs = [(p, mode) for p in sources for mode in args.modes]
    print(f'{len(sources)} programs, {len(jobs)} build pairs; reference vs shared', flush=True)

    def one(item):
        number, (source, mode) = item
        same, accepted = compare(compiler, source, mode, work / str(number))
        return source, mode, same, accepted

    identical = accepted = rejected = 0
    with ThreadPoolExecutor(args.jobs) as pool:
        for count, (source, mode, same, built) in enumerate(pool.map(one, enumerate(jobs)), 1):
            identical += same
            accepted += built
            rejected += not built
            if not same:
                print(f'different: {source.relative_to(ROOT)} {mode}', flush=True)
            if count % 500 == 0:
                print(f'compared {count}/{len(jobs)}', flush=True)
    differences = len(jobs) - identical
    print(f'{identical} identical, {differences} different; '
          f'{accepted} accepted, {rejected} rejected by reference', flush=True)
    if differences:
        print(f'Differences: {work}', flush=True)
    else:
        shutil.rmtree(work)
    return int(differences != 0)


if __name__ == '__main__':
    raise SystemExit(main())
