"""Truncation fuzzing: every prefix of a Dewy source is rejected or accepted, never a panic.

    python3 -m tools.compiler.truncation_fuzz [--per-file N] [--seed N] [--workers N] [-k WORDS]

Each tracked .dewy file (golden cases, examples, ladder and library sources) is cut at random
token boundaries and just before its last token, and `dewy-core check` reads each prefix. A
panic, a crash or a hang is a failure; a diagnostic or a clean check is not. The smallest
prefix of each distinct panic site is kept in the work directory (untracked).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import random
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = Path.home() / 'dev' / 'tmp' / 'dewy-truncation-fuzz'
TIMEOUT = 20


def corpus(words: str = '') -> list[Path]:
    names = subprocess.check_output(['git', 'ls-files', '*.dewy'], cwd=ROOT, text=True)
    return [ROOT / name for name in names.splitlines() if all(w in name for w in words.split())]


def boundaries(source: bytes) -> list[int]:
    """Offsets after a lexeme-like run: a word, a number, a punctuation byte or a quote."""
    cuts = [m.end() for m in re.finditer(rb'[A-Za-z0-9_\x80-\xff]+|[^\sA-Za-z0-9_\x80-\xff]', source)]
    # (never inside a UTF-8 sequence)
    return [c for c in cuts if c < len(source) and source[c] & 0xC0 != 0x80]


def prefixes(source: bytes, per_file: int, rng: random.Random) -> list[int]:
    cuts = boundaries(source)
    if not cuts:
        return []
    chosen = {cuts[-1]} if len(cuts) < 2 else {cuts[-2]}
    chosen.update(rng.sample(cuts, min(per_file, len(cuts))))
    return sorted(chosen)


def environment() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    return {**env, 'DEWY_CORE_LIB': str(ROOT / 'lib'), 'DEWY_EMIT_WORKERS': '1'}


def site(stderr: bytes) -> str:
    """The panic's message and innermost frame, without indexes that vary by input."""
    lines = stderr.decode(errors='replace').splitlines()
    head = re.sub(r'\d+', 'N', lines[0]) if lines else ''
    frame = next((line.strip() for line in lines[1:] if line.strip().startswith('in ')), '')
    return f'{head} | {frame}'


def check(compiler: Path, path: Path) -> tuple[str, bytes]:
    try:
        run = subprocess.run([compiler, 'check', path], cwd=path.parent, env=environment(),
                             capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return 'hang', b''
    if run.stderr.startswith(b'panic:') or b'\npanic:' in run.stderr or run.returncode == 101:
        return 'panic', run.stderr
    if run.returncode < 0 or run.returncode > 1:
        return f'crash {run.returncode}', run.stderr
    return 'ok' if run.returncode == 0 else 'error', run.stderr


def fuzz(compiler: Path, sources: list[Path], per_file: int, seed: int, workers: int,
         work: Path, quiet: bool = False) -> dict:
    shutil.rmtree(work / 'inputs', ignore_errors=True)
    (work / 'inputs').mkdir(parents=True)
    jobs = []
    for index, source in enumerate(sources):
        data = source.read_bytes()
        rng = random.Random(f'{seed}:{source.relative_to(ROOT)}')
        for cut in prefixes(data, per_file, rng):
            jobs.append((source, cut, data[:cut], work / 'inputs' / f'{index}-{cut}.dewy'))

    def one(job):
        source, cut, data, path = job
        path.write_bytes(data)
        verdict, stderr = check(compiler, path)
        if verdict in ('ok', 'error'):
            path.unlink()
        return source, cut, data, verdict, stderr

    counts: dict[str, int] = {}
    failures: dict[str, tuple] = {}
    with ThreadPoolExecutor(workers) as pool:
        for source, cut, data, verdict, stderr in pool.map(one, jobs):
            kind = verdict.split()[0]
            counts[kind] = counts.get(kind, 0) + 1
            if kind in ('ok', 'error'):
                continue
            key = f'{verdict}: {site(stderr)}'
            if key not in failures or len(data) < len(failures[key][1]):
                failures[key] = (source, data, stderr)
    shutil.rmtree(work / 'found', ignore_errors=True)
    (work / 'found').mkdir()
    for number, (key, (source, data, stderr)) in enumerate(sorted(failures.items())):
        (work / 'found' / f'{number}.dewy').write_bytes(data)
        (work / 'found' / f'{number}.stderr').write_bytes(stderr)
        if not quiet:
            print(f'{number}: {key}\n    from {source.relative_to(ROOT)} ({len(data)} bytes)', flush=True)
    if not quiet:
        print(f'{len(jobs)} prefixes of {len(sources)} sources: '
              + ', '.join(f'{n} {k}' for k, n in sorted(counts.items()))
              + f'; {len(failures)} distinct failures in {work / "found"}', flush=True)
    return {'prefixes': len(jobs), 'counts': counts, 'failures': failures}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--compiler', type=Path)
    parser.add_argument('--work', type=Path, default=WORK)
    parser.add_argument('--per-file', type=int, default=4, help='random cuts per source (plus one at its end)')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    parser.add_argument('-k', default='', help='only sources whose path has all these words')
    args = parser.parse_args(argv)
    from tools.core import toolchain
    compiler = args.compiler or toolchain()
    result = fuzz(compiler, corpus(args.k), args.per_file, args.seed, args.workers, args.work)
    return int(bool(result['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
