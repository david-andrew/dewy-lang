"""Build the repository's Dewy core, optionally starting from its C bootstrap."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

if __package__:
    from . import seed_archive
else:  # python3 tools/compiler/build.py
    import seed_archive

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def identity(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_difference(left: Path, right: Path, chunk: int = 1 << 20) -> int | None:
    """The offset of the first byte where two files differ (the shorter length when one is a
    prefix of the other), or None when they are identical."""
    with left.open('rb') as a, right.open('rb') as b:
        offset = 0
        while True:
            x, y = a.read(chunk), b.read(chunk)
            if x != y:
                common = min(len(x), len(y))
                return offset + next((i for i in range(common) if x[i] != y[i]), common)
            if not x:
                return None
            offset += len(x)


def check_fixed_point(binary: Path, rebuild: Callable[[Path, Path], None], *, older_seed: bool = False) -> None:
    """Compare adjacent live builds at the same path. An older G2 may need one extra
    generation before the live compiler stabilizes. Keep the last pair on failure."""
    previous = binary.with_name(binary.name + '.generation-n')
    for _ in range(2 if older_seed else 1):
        binary.replace(previous)
        rebuild(previous, binary)
        at = first_difference(previous, binary)
        if at is None:
            previous.unlink()
            return
    raise RuntimeError(f'not a fixed point: {binary} (generation N+1, {binary.stat().st_size} bytes) differs from '
                       f'{previous} (generation N, {previous.stat().st_size} bytes) at byte offset {at}')


# Written first into every output directory, so a later run may replace one
# (a failed build too) and never a directory that is something else.
OUTPUT_MARKER = '.dewy-build-output'


class OutputDirectoryError(RuntimeError):
    """--output names something that is not an earlier build's output."""


def is_build_output(path: Path) -> bool:
    return path.is_dir() and any((path / name).is_file() for name in (OUTPUT_MARKER, 'build.json'))


def claim_output(output: Path) -> Path | None:
    """Make `output` a new, empty build directory. An earlier build's output there moves to
    `<output>.previous` (replacing the one before it) and its path is returned: the new build
    runs at `output` itself, since the executables embed their own paths. Anything else already
    there is an error, never overwritten."""
    previous = output.with_name(output.name + '.previous')
    if output.exists() or output.is_symlink():
        if not is_build_output(output):
            raise OutputDirectoryError(f'{output} exists and is not the output of an earlier build; pass a new directory to --output')
        if previous.exists() or previous.is_symlink():
            if not is_build_output(previous):
                raise OutputDirectoryError(f'{previous} exists and is not the output of an earlier build; remove it or pass a new directory to --output')
            shutil.rmtree(previous)
        output.rename(previous)
    else:
        previous = None
    output.mkdir(parents=True)
    (output / OUTPUT_MARKER).write_text('')
    return previous


def build(output: Path, *, seed: Path | None = None, bootstrap: bool = False, fixed_point: bool = False,
          seed_cache: Path | None = None, debug_table_growth: bool = False) -> Path:
    """Build into `output`, replacing an earlier build's output there. A failed build keeps both
    its own files (logs, a non-fixed-point pair of executables) and the earlier output, at
    `<output>.previous`."""
    if bootstrap and seed is not None:
        raise ValueError('--bootstrap selects its own pinned seed')
    if seed_cache is not None and not bootstrap:
        raise ValueError('--seed-cache requires --bootstrap')
    output = output.resolve()
    if bootstrap:
        if seed_cache is None:
            seed_cache = ROOT / '__dewycache__' / 'bootstrap-seed'
        seed_cache = seed_cache.resolve()
        if seed_cache.is_relative_to(output):
            raise ValueError('the G2 cache must be outside the replaceable --output directory')
    previous = claim_output(output)
    try:
        binary = build_into(output, seed=seed, bootstrap=bootstrap, fixed_point=fixed_point,
                            seed_cache=seed_cache, debug_table_growth=debug_table_growth)
    except BaseException:
        if previous is not None:
            print(f'build failed; the earlier output is kept at {previous}', file=sys.stderr)
        raise
    if previous is not None:
        shutil.rmtree(previous)
    return binary


def table_growth_sources(output: Path) -> Path:
    """Instrument the compiler build. Programs it emits still use the shipped lib."""
    inputs = output / 'debug-inputs'
    for name in ('compiler', 'lib'):
        shutil.copytree(output / name, inputs / name)
    main = inputs / 'compiler/main.jo'
    runtime = inputs / 'lib/core/rt.jo'
    entry = 'main = ():\n'
    grow = 'q = __grow_alloc(p, 24 + h[1] * es, __arr_bytes(cap, es))'
    main_source, runtime_source = main.read_text(), runtime.read_text()
    if main_source.count(entry) != 1 or runtime_source.count(grow) != 1:
        raise ValueError('the compiler entry or array growth hook changed')
    slots = ''.join(f'    __debug_{name} = (&{name}) as int\n' for name in ('nodes', 'lists', 'types'))
    main.write_text(main_source.replace(entry, entry + slots))
    hook = grow.replace('__grow_alloc(p', '__grow_compiler_array(slot, p')
    runtime.write_text(runtime_source.replace(grow, hook) + '\n' + (HERE / 'debug_table_growth.jo').read_text())
    return inputs


def build_into(output: Path, *, seed: Path | None, bootstrap: bool, fixed_point: bool,
               seed_cache: Path | None = None, debug_table_growth: bool = False) -> Path:
    for name in ('compiler', 'lib'):
        shutil.copytree(ROOT / name, output / name, ignore=shutil.ignore_patterns('sloppy0', '__pycache__'))
    shutil.copy2(ROOT / 'LICENSE', output / 'LICENSE')
    inputs = table_growth_sources(output) if debug_table_growth else output
    sources = {str(p.relative_to(output)): identity(p) for p in sorted(output.rglob('*')) if p.is_file() and p != output / OUTPUT_MARKER}
    binary_dir = output / 'bin'
    binary_dir.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(DEWY_CORE_LIB=str(inputs / 'lib'), DEWY_EMIT_WORKERS='1')
    steps = []

    def run(command, log, cwd=output):
        started = time.perf_counter()
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=180, check=False)
        steps.append({'command': [str(arg) for arg in command],
                      'wall_seconds': time.perf_counter() - started,
                      'returncode': result.returncode})
        (output / log).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'{log}:\n{result.stdout}{result.stderr}')

    bootstrap_hashes = []
    provenance = {'debug_table_growth': True} if debug_table_growth else {}
    if bootstrap:
        assert seed_cache is not None  # resolved before claiming output
        seed, pin = seed_archive.obtain(seed_cache, log=output / 'archive-bootstrap.log')
        provenance['seed_archive'] = pin
        if not pin['cache_hit']:
            steps.append(pin.pop('build_step'))
            bootstrap_hashes = list(pin['built_sha256'].values())
    if seed is None:
        raise ValueError('provide --seed or --bootstrap')
    seed = seed.resolve(strict=True)
    binary = binary_dir / 'dewy-core'
    run([seed, 'build', inputs / 'compiler/main.jo', '-o', binary],
        'self-build.log' if bootstrap else 'core-build.log')
    if fixed_point or bootstrap:
        generations = [identity(binary)]

        def rebuild(compiler: Path, target: Path) -> None:
            log = 'fixed-point.log' if len(generations) == 1 else 'fixed-point-2.log'
            run([compiler, 'build', inputs / 'compiler/main.jo', '-o', target], log)
            generations.append(identity(target))

        check_fixed_point(binary, rebuild, older_seed=bootstrap)
        provenance['live_generations_sha256'] = generations
    (output / 'build.json').write_text(json.dumps({
        'seed_sha256': identity(seed),
        'core_sha256': identity(binary),
        'sources_sha256': sources,
        'bootstrap_generations_sha256': bootstrap_hashes,
        'build_steps': steps,
        **provenance,
    }, indent=2) + '\n')
    return binary


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    seeds = cli.add_mutually_exclusive_group(required=True)
    seeds.add_argument('--seed', type=Path, help='existing native Dewy core compiler')
    seeds.add_argument('--bootstrap', '--bootstrap-archive', action='store_true', help='build with the pinned G2 and verify live convergence')
    cli.add_argument('--seed-cache', type=Path, help='G2 cache for --bootstrap (default: __dewycache__/bootstrap-seed)')
    cli.add_argument('--output', type=Path, required=True, help='directory for the standalone toolchain (an earlier build'"'"'s output there is replaced)')
    cli.add_argument('--fixed-point', action='store_true',
                     help='rebuild the compiler with itself and fail unless the bytes are identical')
    cli.add_argument('--debug-table-growth', action='store_true',
                     help='move compiler tables on capacity growth and poison retired buffers')
    args = cli.parse_args()
    if args.seed_cache is not None and not args.bootstrap:
        cli.error('--seed-cache requires --bootstrap')
    try:
        print(build(args.output, seed=args.seed, bootstrap=args.bootstrap, fixed_point=args.fixed_point,
                    seed_cache=args.seed_cache, debug_table_growth=args.debug_table_growth))
    except OutputDirectoryError as error:
        raise SystemExit(f'build.py: {error}') from None
