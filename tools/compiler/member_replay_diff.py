"""Compare members checking/lowering with the expanded reference.

The same compiler, source path, output path, and library are used in all three modes.
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
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[2]
MODES = {'native': [], 'release': ['--release'], 'g': ['-g'],
         'wasm32': ['--target', 'wasm32'], 'aarch64-mac': ['--target', 'aarch64-mac'],
         'x86_64-windows': ['--target', 'x86_64-windows']}


def programs() -> list[Path]:
    return sorted(set([*(ROOT / 'tests/cases').rglob('*.dewy'),
                       *(ROOT / 'examples').glob('*.dewy'),
                       *(ROOT / 'tests/ladder').glob('*/core.dewy'),
                       *(ROOT / 'tests/ladder').glob('*/design.dewy')]))


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.inside = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


def run_program(output: Path, mode: str, env: dict) -> tuple[int, bytes, bytes] | None:
    """None means a foreign OS format; its files must remain byte-identical."""
    binary = output / 'program'
    if mode == 'wasm32':
        node = shutil.which('node')
        if node is None:
            raise RuntimeError('Node is required for members-loop runtime equivalence')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = output / 'runner.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    elif mode == 'aarch64-mac' and platform.system() != 'Darwin':
        return None
    elif mode == 'x86_64-windows' and platform.system() != 'Windows':
        return None
    else:
        command = [binary.with_suffix('.exe') if mode == 'x86_64-windows' else binary]
    run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=30)
    return run.returncode, run.stdout, run.stderr


def compare(compiler: Path, source: Path, mode: str, directory: Path, *,
            execute: bool = False, panic: bytes | None = None,
            allow_lowering: bool = False) -> tuple[bool, bool]:
    """(equivalent, accepted). Checking alone must retain exact output files.

    Shared lowering must retain diagnostics and either files or runtime results.
    Corpus callers can explicitly allow differing files for traced qualifying
    loops without executing arbitrary (possibly interactive) programs. Foreign
    OS formats always require file identity; no runtime equivalence is inferred
    from a successful cross-build. Panics compare status and complete output.
    """
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / 'out'
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(DEWY_CORE_LIB=str(ROOT / 'lib'), DEWY_EMIT_WORKERS='1')
    results = []
    executions = []
    folded = False
    trace = []
    for selection in ('reference', 'checked', 'trace'):
        shutil.rmtree(output, ignore_errors=True)
        output.mkdir()
        run = subprocess.run([compiler, 'build', source, '-o', output / 'program', *MODES[mode]],
                             cwd=ROOT, env=env | {'DEWY_MEMBERS': selection},
                             capture_output=True, timeout=180, check=False)
        stderr = run.stderr
        if selection == 'trace':
            lines = stderr.splitlines(keepends=True)
            trace = [line for line in lines if line.startswith(
                (b'member syntax rejected ', b'member template ', b'member lowering '))]
            stderr = b''.join(line for line in lines if line not in trace)
            folded = any(line.startswith(b'member lowering ') and b': true,' in line for line in trace)
        files = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in output.rglob('*') if p.is_file()}
        results.append((run.returncode, run.stdout, stderr, files))
        if execute and run.returncode == 0 and selection != 'checked':
            executions.append(run_program(output, mode, env))
    identical = results[0] == results[1] and results[0][:3] == results[2][:3]
    files_equal = results[0][3] == results[2][3]
    identical &= files_equal or folded and (execute or allow_lowering)
    if execute and results[0][0] == 0:
        identical &= len(executions) == 2 and executions[0] == executions[1]
        if executions[0] is None:
            identical &= files_equal
        elif panic is None:
            identical &= executions[0][0] == 0
        else:
            status, stdout, stderr = executions[0]
            identical &= status != 0 and panic in stdout + stderr
    if identical:
        shutil.rmtree(directory)
    else:
        (directory / 'source.txt').write_text(f'{source}\n{mode}\n')
        (directory / 'trace.stderr').write_bytes(b''.join(trace))
        (directory / 'executions.txt').write_text(repr(executions) + '\n')
        for selection, (status, stdout, stderr, files) in zip(('reference', 'checked', 'shared'), results):
            (directory / f'{selection}.stdout').write_bytes(stdout)
            (directory / f'{selection}.stderr').write_bytes(stderr)
            (directory / f'{selection}.files').write_text(f'exit {status}\n' + '\n'.join(
                f'{digest} {name}' for name, digest in sorted(files.items())) + '\n')
    return identical, results[0][0] == 0


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--compiler', type=Path)
    cli.add_argument('--modes', nargs='+', choices=MODES, default=['native'])
    cli.add_argument('--allow-lowering', action='store_true',
                     help='allow traced folded loops to change files; compare all diagnostics, without running the corpus')
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
    print(f'{len(sources)} programs, {len(jobs)} build triples; reference vs checked vs shared', flush=True)

    def one(item):
        number, (source, mode) = item
        same, accepted = compare(compiler, source, mode, work / str(number), allow_lowering=args.allow_lowering)
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
    print(f'{identical} matching, {differences} different; '
          f'{accepted} accepted, {rejected} rejected by reference', flush=True)
    if differences:
        print(f'Differences: {work}', flush=True)
    else:
        shutil.rmtree(work)
    return int(differences != 0)


if __name__ == '__main__':
    raise SystemExit(main())
