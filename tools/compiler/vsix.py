"""Package the VS Code extension, optionally for one platform with a toolchain bundled.

    python -m tools.compiler.vsix --output dewy.vsix
    python -m tools.compiler.vsix --target linux-x64 --toolchain dewy-core-linux-x86_64.tar.gz \\
        --output dewy-linux-x64.vsix

A platform package carries the tested toolchain archive that tools.compiler.package made, verified
against its PACKAGE.json, as toolchain/ beside the extension: the extension runs
toolchain/bin/dewy-core when dewy.core.path is not set. The universal package has no toolchain
and finds an installed compiler instead. editors/vscode itself is not modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / 'editors' / 'vscode'
VSCE = '@vscode/vsce@3'

# VS Code platform targets and the toolchain hosts (tools.compiler.package) that serve them.
TARGETS = {
    'linux-x64': 'linux-x86_64',
    'linux-arm64': 'linux-arm64',
    'darwin-arm64': 'macos',
    'win32-x64': 'windows',
}


def unpack_toolchain(archive: Path, target: str, destination: Path) -> None:
    with tarfile.open(archive) as stream:
        members = {m.name: m for m in stream.getmembers() if m.isfile()}
        manifest = json.loads(stream.extractfile(members['dewy-core/PACKAGE.json']).read())
        if manifest.get('host') != TARGETS[target]:
            raise ValueError(f'{archive.name} is for {manifest.get("host")}, not {target}')
        for name, sha in manifest['files'].items():
            member = members.get(f'dewy-core/{name}')
            if member is None:
                raise ValueError(f'{archive.name} lacks {name}')
            data = stream.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError(f'{archive.name}: {name} does not match PACKAGE.json')
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if name.startswith('bin/') else 0o644)


def package(output: Path, target: str | None = None, toolchain: Path | None = None,
            vsce: list[str] | None = None) -> Path:
    if (target is None) != (toolchain is None):
        raise ValueError('a platform package needs both --target and --toolchain')
    if target is not None and target not in TARGETS:
        raise ValueError(f'unknown target {target}; one of {", ".join(TARGETS)}')
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dewy-vsix-', dir=output.parent) as scratch:
        stage = Path(scratch) / 'extension'
        shutil.copytree(EXTENSION, stage, ignore=shutil.ignore_patterns('toolchain', 'node_modules', '*.vsix'))
        if toolchain is not None:
            unpack_toolchain(toolchain.resolve(strict=True), target, stage / 'toolchain')
            manifest = json.loads((stage / 'package.json').read_text())
            manifest['files'].append('toolchain/**')
            (stage / 'package.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
        command = list(vsce or ['npx', '--yes', VSCE]) + ['package', '--out', str(output)]
        if target is not None:
            command += ['--target', target]
        npx = shutil.which(command[0])
        if npx is None:
            raise RuntimeError(f'{command[0]} is not installed (Node.js is needed to package the extension)')
        subprocess.run([npx, *command[1:]], cwd=stage, check=True,
                       env={**os.environ, 'npm_config_update_notifier': 'false'})
    return output


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--output', type=Path, required=True, help='the .vsix to write')
    cli.add_argument('--target', choices=sorted(TARGETS), help='VS Code platform of a toolchain package')
    cli.add_argument('--toolchain', type=Path, help='toolchain archive from tools.compiler.package')
    args = cli.parse_args()
    print(package(args.output, args.target, args.toolchain))
