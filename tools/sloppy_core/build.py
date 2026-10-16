"""Build the repository's Dewy core, optionally starting from its C bootstrap."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from udewy.cache import cache_artifact

PIN = '235e19a271bccad3fe72e36d03264807a632dc1b'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORE = ROOT / 'core'


def identity(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output: Path, *, dewy: Path | None = None, parser: Path | None = None,
          seed: Path | None = None, bootstrap: bool = False, legacy_parser: bool = False) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ('compiler', 'lib', 'stage0', 'bootstrap'):
        shutil.copytree(CORE / name, output / name, ignore=shutil.ignore_patterns('sloppy0'))
    for name in ('LICENSE', 'NOTICE', 'UPSTREAM.json'):
        shutil.copy2(CORE / name, output / name)
    sources = {str(p.relative_to(output)): identity(p) for p in sorted(output.rglob('*')) if p.is_file()}
    binary_dir = output / 'bin'
    binary_dir.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_LIBRARY_ROOT=str(ROOT / 'library'), SLOPPY_LIB=str(output / 'lib'),
               SLOPPY_EMIT_WORKERS='1')
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

    native_parser = binary_dir / 'dewy-parse'
    if parser is not None:
        shutil.copy2(parser.resolve(strict=True), native_parser)
    elif dewy is not None:
        dewy = dewy.resolve(strict=True)
        work = output / 'parser-build'
        work.mkdir()
        source = HERE / 'parse.dewy'
        run([dewy, '-c', source], 'parser-build.log', cwd=work)
        shutil.copy2(work / cache_artifact(source, cwd=work), native_parser)
    elif legacy_parser:
        source = output / 'bootstrap/dewy_parse.c'
        source.write_bytes(gzip.decompress((output / 'bootstrap/dewy_parse.c.gz').read_bytes()))
        cc = shlex.split(os.environ.get('CC', 'cc'))
        run([*cc, '-std=c99', '-O1', source, '-o', native_parser, '-lm'], 'parser-c-build.log')
    bootstrap_hashes = []
    if bootstrap:
        # Build the implementation-language frontend first. This permits the
        # main compiler to use features outside the intentionally small C seed.
        frontend = output / 'compiler/frontend.jo'
        shutil.copy2(CORE / 'bootstrap/frontend.jo', frontend)
        stage0 = output / 'stage0/sloppy0'
        seed = binary_dir / 'core-bootstrap'
        try:
            run(['make', '-s', '-C', str(output / 'stage0')], 'bootstrap-c.log')
            run([stage0, output / 'compiler/main.jo', '-o', seed], 'bootstrap-core.log')
        finally:
            shutil.copy2(CORE / 'compiler/frontend.jo', frontend)
        bootstrap_hashes = [identity(p) for p in (stage0, seed)]
    if seed is None:
        raise ValueError('provide --seed or --bootstrap')
    seed = seed.resolve(strict=True)
    binary = binary_dir / 'dewy-core'
    run([seed, 'build', output / 'compiler/main.jo', '-o', binary], 'core-build.log')
    if bootstrap:
        first_core = binary_dir / 'dewy-core-bootstrap'
        binary.rename(first_core)
        bootstrap_hashes.append(identity(first_core))
        run([first_core, 'build', output / 'compiler/main.jo', '-o', binary], 'self-build.log')
    (output / 'build.json').write_text(json.dumps({
        'upstream_revision': PIN, 'seed_sha256': identity(seed),
        'dewy_seed_sha256': identity(dewy) if dewy else None,
        'default_frontend': 'in-process',
        'parser_sha256': identity(native_parser) if native_parser.exists() else None,
        'core_sha256': identity(binary),
        'parser_source_sha256': identity(HERE / 'parse.dewy') if dewy else None,
        'sources_sha256': sources,
        'bootstrap_generations_sha256': bootstrap_hashes,
        'build_steps': steps,
    }, indent=2) + '\n')
    return binary


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    parsers = cli.add_mutually_exclusive_group()
    parsers.add_argument('--legacy-parser', action='store_true', help='also build the optional legacy C syntax parser')
    parsers.add_argument('--dewy', type=Path, help='native Dewy seed used to build the syntax parser')
    parsers.add_argument('--parser', type=Path, help='reuse an already built dewy-parse binary')
    seeds = cli.add_mutually_exclusive_group(required=True)
    seeds.add_argument('--seed', type=Path, help='existing native Sloppy or Dewy core compiler')
    seeds.add_argument('--bootstrap', action='store_true', help='build from the independent C bootstrap')
    cli.add_argument('--output', type=Path, required=True, help='new directory for the standalone toolchain')
    args = cli.parse_args()
    print(build(args.output, dewy=args.dewy, parser=args.parser, seed=args.seed,
                bootstrap=args.bootstrap, legacy_parser=args.legacy_parser))
