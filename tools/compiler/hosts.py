"""Prepare cross-built compiler bundles for the CI host execution checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path


# Each host bundle's compiler target name.
TARGETS = {'windows': 'x86_64-windows', 'macos': 'aarch64-mac', 'linux-arm64': 'aarch64-linux'}


def build(toolchain: Path, output: Path) -> None:
    toolchain = toolchain.resolve(strict=True)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    compiler = toolchain / 'bin/dewy-core'
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('DEWY_')}
    env.update(DEWY_CORE_LIB=str(toolchain / 'lib'), DEWY_EMIT_WORKERS='1')
    for host, target in TARGETS.items():
        bundle = output / host / 'dewy-core'
        (bundle / 'bin').mkdir(parents=True)
        binary = bundle / 'bin' / ('dewy-core.exe' if host == 'windows' else 'dewy-core')
        command = [compiler, 'build', toolchain / 'compiler/main.jo', '--target', target, '-o', binary]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=90, check=False)
        (output / f'{host}.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'{host} compiler build failed:\n{result.stdout}{result.stderr}')
        shutil.copytree(toolchain / 'lib', bundle / 'lib')
        shutil.copy2(toolchain / 'LICENSE', bundle / 'LICENSE')
        provenance = {
            'host': host,
            'cross_compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
            'compiler_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'source_build': json.loads((toolchain / 'build.json').read_text()),
        }
        (bundle / 'HOST_BUILD.json').write_text(json.dumps(provenance, indent=2) + '\n')
        archive = output / f'{host}.tar.gz'
        with tarfile.open(archive, 'x:gz') as stream:
            stream.add(bundle, arcname='dewy-core')
        print(archive, flush=True)


def extract(archive: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as stream:
        stream.extractall(output, filter='data')


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('build')
    prepare.add_argument('toolchain', type=Path)
    prepare.add_argument('--output', type=Path, required=True)
    unpack = commands.add_parser('extract')
    unpack.add_argument('archive', type=Path)
    unpack.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    if args.command == 'build':
        build(args.toolchain, args.output)
    else:
        extract(args.archive, args.output)
