"""Compare reader behavior across two compiler revisions on tracked and generated sources.

    python3 -m tools.compiler.parser_diff --reference /path/to/previous/dewy-core
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import random
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = Path.home() / 'dev/tmp/dewy-parser-diff'


def environment(lib: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    return {**env, 'DEWY_CORE_LIB': str(lib), 'DEWY_EMIT_WORKERS': '1'}


def build_reader(seed: Path, work: Path, release: bool) -> Path:
    tree = work / 'source'
    shutil.rmtree(tree, ignore_errors=True)
    shutil.copytree(ROOT / 'compiler', tree / 'compiler')
    shutil.copytree(ROOT / 'lib', tree / 'lib')
    # The compiler's own build block selects release. Remove it in both copies
    # so the default pair really exercises the default compiler build as well.
    main = tree / 'compiler/main.jo'
    main.write_text(main.read_text().replace('build:\n    opt = release\n', ''))
    mode = 'release' if release else 'default'
    binary = work / f'dewy-{mode}'
    run = subprocess.run([seed, 'build', main, '-o', binary, *(['--release'] if release else [])],
                         cwd=ROOT, env=environment(tree / 'lib'), capture_output=True, timeout=300)
    log = work / f'build-dewy-{mode}.log'
    log.write_bytes(run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError(f'reader did not build; see {log}')
    return binary


def generated(directory: Path, count: int, seed: int = 417) -> list[Path]:
    from tools.compiler import dewy_fuzz_programs as gen

    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for number in range(seed, seed + count):
        program, _ = gen.generate(number)
        source = program.render().encode()
        rng = random.Random(number)
        cut = rng.randrange(len(source) + 1)
        variants = [source, source[:cut], source[:cut] + b'}])' + source[cut:],
                    source[:cut] + b'"{if true {"{1}"} else {"x"}}"' + source[cut:]]
        for index, data in enumerate(variants):
            path = directory / f'seed-{number}-{index}.dewy'
            path.write_bytes(data)
            paths.append(path)
    # Byte preservation, interpolation, token splitting and partial parser rollback.
    edges = [b'printl("\xff")\n', b'printl("{1 + }")\n', b'let x="{[1 2][0]}"\n',
             b'let x:array<array<int64>>=[[1]]\nprintl(x[0][0])\n',
             b'let x=if true {"{if false 1 else 2}"} else "x"\nprintl(x)\n',
             b'f=(x:array<int64>):>int64=>x[0]\nprintl(f([3]))\n',
             b'printl("{\xff}")\n', b'let x=(\n', b'$target.x86_64 {let x=1}\n',
             # Truncated text: lookahead past the end, a range left unread, a comma list cut off.
             b'f=(x:int64 y', b'main=():>void=>{\n    let', b'if [1..5', b'printl(max(1, 2',
             b'main=():>void=>{\n    $assert(x[[..', b'let f:']
    for index, data in enumerate(edges):
        path = directory / f'edge-{index}.dewy'
        path.write_bytes(data)
        paths.append(path)
    return paths


def corpus() -> list[Path]:
    names = subprocess.check_output(['git', 'ls-files', '*.dewy'], cwd=ROOT, text=True)
    return [ROOT / name for name in names.splitlines()]


def compare(pair: tuple[Path, ...], sources: list[Path], work: Path,
            release: bool, workers: int, observe=None) -> list[tuple[Path, str]]:
    """Keep binary, library, input and output paths identical across the two sides.
    observe(source, directory, run), when given, sees each build of the first side before its outputs go;
    a one-sided pair has nothing to differ from."""
    active = work / 'active'
    active.mkdir(exist_ok=True)
    binary = active / 'dewy-core'
    outputs = work / 'outputs'
    env = environment(ROOT / 'lib')

    def one(item):
        index, source = item
        directory = outputs / str(index)
        directory.mkdir(parents=True)
        run = subprocess.run([binary, 'build', source, '-o', directory / 'program',
                              *(['--release'] if release else [])], cwd=ROOT, env=env,
                             capture_output=True, timeout=180)
        if observe and side is pair[0]:
            observe(source, directory, run)
        files = tuple((str(p.relative_to(directory)), hashlib.sha256(p.read_bytes()).digest())
                      for p in sorted(directory.rglob('*')) if p.is_file())
        shutil.rmtree(directory)
        return run.returncode, run.stdout, run.stderr, files

    results = []
    for side in pair:
        shutil.copy2(side, binary)
        shutil.rmtree(outputs, ignore_errors=True)
        outputs.mkdir()
        with ThreadPoolExecutor(workers) as pool:
            results.append(list(pool.map(one, enumerate(sources))))
    failures = []
    for source, left, right in zip(sources, *results) if len(pair) == 2 else ():
        if left == right:
            continue
        reason = ', '.join(name for name, a, b in zip(
            ('status', 'stdout', 'stderr', 'emitted files'), left, right) if a != b)
        failures.append((source, reason))
        directory = work / f'difference-{len(failures)}'
        directory.mkdir(exist_ok=True)
        (directory / 'source').write_text(str(source))
        for label, result in zip(('candidate', 'reference'), (left, right)):
            (directory / f'{label}.stdout').write_bytes(result[1])
            (directory / f'{label}.stderr').write_bytes(result[2])
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path)
    parser.add_argument('--reference', required=True, type=Path, help='compiler to compare against')
    parser.add_argument('--work', type=Path, default=WORK)
    parser.add_argument('--generated', type=int, default=128)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=2)
    parser.add_argument('-k', default='', help='filter the tracked corpus by path substring')
    args = parser.parse_args(argv)
    from tools.core import toolchain
    seed = args.compiler or toolchain()
    args.work.mkdir(parents=True, exist_ok=True)
    sources = [p for p in corpus() if args.k in str(p)]
    sources += generated(args.work / 'generated', args.generated)
    failed = False
    for release in (False, True):
        mode = 'release' if release else 'default'
        work = args.work / mode
        work.mkdir(exist_ok=True)
        pair = (seed, args.reference)
        failures = compare(pair, sources, work, release, args.workers)
        for source, reason in failures:
            print(f'{mode}: {source}: {reason}', flush=True)
        print(f'{mode}: {len(sources)} sources, {len(failures)} differences', flush=True)
        failed |= bool(failures)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
