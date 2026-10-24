"""Byte identity: every example (examples/*.dewy) and ladder program (tests/ladder/*/core.dewy)
built by a base commit's compiler and by this checkout's, in each mode (native, --release, -g,
wasm32, aarch64-mac, x86_64-windows), gives the same files. For a change that must not change
what the compiler writes, such as moving a compiler module to Dewy.

Each compiler is its commit's fixed point with its own library (tools/compiler/speed.py), and
each is copied to one fixed path in turn, and builds into one fixed directory, so the paths the
outputs hold match. Inputs are this checkout's. A program neither compiler builds in a mode is
skipped; one only one of them builds is a difference.

    python3 -m tools.compiler.same_output [--base master] [--jobs 4] [-k WORD]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.compiler import speed

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '__dewycache__' / 'same_output'
MODES = {'native': [], 'release': ['--release'], 'g': ['-g'], 'wasm32': ['--target', 'wasm32'],
         'aarch64-mac': ['--target', 'aarch64-mac'], 'x86_64-windows': ['--target', 'x86_64-windows']}


def programs() -> list[Path]:
    found = sorted((ROOT / 'examples').glob('*.dewy'))
    found += sorted(p for p in (ROOT / 'tests/ladder').glob('*/core.dewy'))
    return found


def build_all(binary: Path, lib: Path, jobs: list[tuple[Path, str]], out: Path, workers: int) -> dict:
    """Stage the toolchain at the fixed path and build every job into out: (program, mode) -> built."""
    active = WORK / 'active'
    shutil.rmtree(active, ignore_errors=True)
    (active / 'bin').mkdir(parents=True)
    shutil.copy2(binary, active / 'bin/dewy-core')
    shutil.copytree(lib, active / 'lib')
    shutil.rmtree(out, ignore_errors=True)
    env = speed.clean_env(DEWY_CORE_LIB=str(active / 'lib'))

    def one(job):
        source, mode = job
        target = out / source.relative_to(ROOT).with_suffix('') / mode
        target.mkdir(parents=True)
        run = subprocess.run([active / 'bin/dewy-core', 'build', source, '-o', target / 'program', *MODES[mode]],
                             cwd=ROOT, env=env, capture_output=True, timeout=600)
        return job, run.returncode == 0

    with ThreadPoolExecutor(workers) as pool:
        return dict(pool.map(one, jobs))


def files(directory: Path) -> dict[str, bytes]:
    return {str(p.relative_to(directory)): p.read_bytes() for p in sorted(directory.rglob('*')) if p.is_file()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='same_output', description=__doc__.split('\n\n')[0])
    parser.add_argument('--base', default='master', help='the commit to compare with (default master)')
    parser.add_argument('--jobs', type=int, default=4, help='programs built at once (default 4)')
    parser.add_argument('-k', dest='words', action='append', default=[], help='only programs whose path has WORD')
    args = parser.parse_args(argv)
    from tools.core import toolchain

    current = toolchain()
    revision = speed.git('rev-parse', args.base)
    base_dir, _ = speed.base_compiler(revision, current)
    candidate = speed.candidate_compiler(current)
    sources = [p for p in programs() if not args.words or any(w in str(p) for w in args.words)]
    jobs = [(p, mode) for p in sources for mode in MODES]
    print(f'{len(sources)} programs x {len(MODES)} modes: base {revision[:10]}, then this checkout', flush=True)
    base_out, out = WORK / 'base', WORK / 'out'
    built = build_all(base_dir / 'bin/dewy-core', base_dir / 'lib', jobs, out, args.jobs)
    shutil.rmtree(base_out, ignore_errors=True)
    out.replace(base_out)
    now = build_all(candidate, ROOT / 'lib', jobs, out, args.jobs)
    differ, same, neither, count = [], 0, 0, 0
    for source, mode in jobs:
        name = f'{source.relative_to(ROOT)} {mode}'
        if built[source, mode] != now[source, mode]:
            differ.append(f'{name}: built by {"the base" if built[source, mode] else "this checkout"} only')
        elif not built[source, mode]:
            neither += 1
        else:
            rel = source.relative_to(ROOT).with_suffix('') / mode
            old = files(base_out / rel)
            if old and old == files(out / rel):
                same += 1
                count += len(old)
            else:
                differ.append(f'{name}: the outputs differ')
    for line in differ:
        print(line)
    print(f'{same} builds identical ({count} files), {len(differ)} different, {neither} built by neither')
    if not differ:
        shutil.rmtree(WORK, ignore_errors=True)
    return 1 if differ else 0


if __name__ == '__main__':
    sys.exit(main())
