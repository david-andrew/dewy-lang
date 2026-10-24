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

# The bootstrap chain, and the compiler modules written in Dewy:
#   1. stage0/ (C) builds core-bootstrap from compiler/, with bootstrap/'s
#      frontends in place of compiler/'s: it has no Dewy frontend.
#   2. core-bootstrap builds dewy-core-bootstrap from compiler/: the first
#      compiler with the Dewy frontend.
#   3. dewy-core-bootstrap builds dewy-core from compiler/, which builds itself
#      byte-identically (the fixed point). A --seed build is this step alone.
# Steps 1 and 2 cannot read Dewy, so there every `use 'X.dewy'` in compiler/
# names X.dewy's frozen implementation-language twin instead. Steps 3 on
# compile the Dewy modules, so the compiler that ships runs them.
FROZEN_TWINS = {'zip.dewy': 'zip.jo', 'spelling.dewy': 'spelling.jo', 'leb128.dewy': 'leb128.jo',
               'base64.dewy': 'base64.jo', 'line_table.dewy': 'line_table.jo', 'sha.dewy': 'sha.jo',
               'icns.dewy': 'icns.jo', 'targets.dewy': 'targets.jo'}


def identity(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def use_frozen_twins(compiler: Path) -> dict[Path, str]:
    """Point compiler/'s imports of its Dewy modules at their twins; return the originals."""
    originals = {}
    for module, twin in FROZEN_TWINS.items():
        line = f"use '{module}'\n"
        importers = [path for path in sorted(compiler.glob('*.jo')) if line in path.read_text()]
        if not importers:
            raise RuntimeError(f'no compiler module uses {module}; update FROZEN_TWINS')
        for path in importers:
            text = path.read_text()
            originals.setdefault(path, text)
            path.write_text(text.replace(line, f"use '{twin}'\n"))
    return originals


def build(output: Path, *, seed: Path | None = None, bootstrap: bool = False) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ('compiler', 'lib', 'stage0', 'bootstrap'):
        shutil.copytree(ROOT / name, output / name, ignore=shutil.ignore_patterns('sloppy0', '__pycache__'))
    shutil.copy2(ROOT / 'LICENSE', output / 'LICENSE')
    sources = {str(p.relative_to(output)): identity(p) for p in sorted(output.rglob('*')) if p.is_file()}
    binary_dir = output / 'bin'
    binary_dir.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(DEWY_CORE_LIB=str(output / 'lib'), DEWY_EMIT_WORKERS='1')
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
        first_core = binary_dir / 'dewy-core-bootstrap'
        originals = use_frozen_twins(output / 'compiler')
        try:
            run(['make', '-s', '-C', str(output / 'stage0')], 'bootstrap-c.log')
            run([stage0, output / 'compiler/main.jo', '-o', seed], 'bootstrap-core.log')
        finally:
            for name in bootstrap_modules:
                shutil.copy2(ROOT / 'compiler' / name, output / 'compiler' / name)
        try:
            run([seed, 'build', output / 'compiler/main.jo', '-o', first_core], 'core-build.log')
        finally:
            for path, text in originals.items():
                path.write_text(text)
        bootstrap_hashes = [identity(p) for p in (stage0, seed, first_core)]
        seed = first_core
    if seed is None:
        raise ValueError('provide --seed or --bootstrap')
    seed = seed.resolve(strict=True)
    binary = binary_dir / 'dewy-core'
    try:
        run([seed, 'build', output / 'compiler/main.jo', '-o', binary],
            'self-build.log' if bootstrap else 'core-build.log')
    except RuntimeError as direct:
        if bootstrap:
            raise
        # An older seed may not read the Dewy modules (or the library they
        # reach) as the sources now write them: build through their twins,
        # then let that compiler build the sources as they are.
        interim = binary_dir / 'dewy-core-interim'
        originals = use_frozen_twins(output / 'compiler')
        try:
            run([seed, 'build', output / 'compiler/main.jo', '-o', interim], 'interim-build.log')
        except RuntimeError:
            raise direct from None
        finally:
            for path, text in originals.items():
                path.write_text(text)
        run([interim, 'build', output / 'compiler/main.jo', '-o', binary], 'core-build.log')
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
    seeds.add_argument('--seed', type=Path, help='existing native Dewy core compiler')
    seeds.add_argument('--bootstrap', action='store_true', help='build from the independent C bootstrap')
    cli.add_argument('--output', type=Path, required=True, help='new directory for the standalone toolchain')
    args = cli.parse_args()
    print(build(args.output, seed=args.seed, bootstrap=args.bootstrap))
