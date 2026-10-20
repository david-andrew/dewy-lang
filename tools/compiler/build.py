"""Build the repository's Dewy core, optionally starting from its C bootstrap."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORIGIN = ROOT / 'docs/origin'


def identity(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output: Path, *, seed: Path | None = None, bootstrap: bool = False) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ('compiler', 'lib', 'stage0', 'bootstrap'):
        shutil.copytree(ROOT / name, output / name, ignore=shutil.ignore_patterns('sloppy0', '__pycache__'))
    for name in ('LICENSE', 'NOTICE'):
        shutil.copy2(ORIGIN / name, output / name)
    sources = {str(p.relative_to(output)): identity(p) for p in sorted(output.rglob('*')) if p.is_file()}
    binary_dir = output / 'bin'
    binary_dir.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_LIB=str(output / 'lib'), SLOPPY_EMIT_WORKERS='1')
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
    if bootstrap:
        # Build the implementation-language frontend first. This permits the
        # main compiler to use features outside the intentionally small C seed.
        bootstrap_modules = ('frontend.jo', 'dewy_fmt.jo')
        for name in bootstrap_modules:
            shutil.copy2(ROOT / 'bootstrap' / name, output / 'compiler' / name)
        stage0 = output / 'stage0/sloppy0'
        seed = binary_dir / 'core-bootstrap'
        try:
            run(['make', '-s', '-C', str(output / 'stage0')], 'bootstrap-c.log')
            run([stage0, output / 'compiler/main.jo', '-o', seed], 'bootstrap-core.log')
        finally:
            for name in bootstrap_modules:
                shutil.copy2(ROOT / 'compiler' / name, output / 'compiler' / name)
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
        'seed_sha256': identity(seed),
        'core_sha256': identity(binary),
        'sources_sha256': sources,
        'bootstrap_generations_sha256': bootstrap_hashes,
        'build_steps': steps,
    }, indent=2) + '\n')
    return binary


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    seeds = cli.add_mutually_exclusive_group(required=True)
    seeds.add_argument('--seed', type=Path, help='existing native Sloppy or Dewy core compiler')
    seeds.add_argument('--bootstrap', action='store_true', help='build from the independent C bootstrap')
    cli.add_argument('--output', type=Path, required=True, help='new directory for the standalone toolchain')
    args = cli.parse_args()
    print(build(args.output, seed=args.seed, bootstrap=args.bootstrap))
