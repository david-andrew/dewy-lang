"""Package a built Linux x86-64 core and its libraries for use without Python."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path

README = """Dewy compact core — development toolchain for Linux x86-64

Keep bin/ and lib/ together; the compiler finds its libraries beside itself.
The extracted directory can be moved. Running the compiler requires neither
Python nor a C compiler.

From this directory:
  ./bin/dewy-core --version
  ./bin/dewy-core new my-game
  ./bin/dewy-core build my-game/main.dewy -o my-game-native
  ./bin/dewy-core build my-game/main.dewy --target wasm -o my-game-web
  ./bin/dewy-core watch my-game/main.dewy

Open my-game-web.html in a browser, or run ./my-game-native on a Linux desktop.
The compiler also accepts ordinary .dewy programs and an interactive `repl`.
Use an absolute path to bin/dewy-core when working from another directory.

This is the experimental compact core. Language and platform coverage:
https://github.com/david-andrew/dewy-lang/blob/restart/sloppy-frontend/core/README.md

PACKAGE.json records the payload hashes and an optional source revision.
build.json records the compiler build and source provenance.
"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package(toolchain: Path, output: Path, *, revision: str | None = None) -> Path:
    toolchain = toolchain.resolve(strict=True)
    manifest = json.loads((toolchain / 'build.json').read_text())
    expected = {'bin/dewy-core': manifest['core_sha256']}
    expected.update({name: sha for name, sha in manifest['sources_sha256'].items()
                     if name.startswith('lib/')})
    for name in ('LICENSE', 'NOTICE', 'UPSTREAM.json'):
        expected[name] = manifest['sources_sha256'][name]
    if 'lib/core/rt.jo' not in expected:
        raise ValueError('build manifest has no standard library')
    # Package exactly the tested payload, excluding bootstrap executables and
    # incidental files created beside a toolchain during local development.
    payload = {}
    for name, sha in expected.items():
        data = (toolchain / name).read_bytes()
        if digest(data) != sha:
            raise ValueError(f'toolchain changed since its build: {name}')
        payload[name] = data
    payload['build.json'] = (toolchain / 'build.json').read_bytes()
    payload['README.txt'] = README.encode()
    metadata = {'format': 1, 'host': 'linux-x86_64', 'revision': revision,
                'files': {name: digest(data) for name, data in payload.items()}}
    payload['PACKAGE.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids replacing an earlier artifact accidentally.
    with output.open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, data in sorted(payload.items()):
            member = tarfile.TarInfo(f'dewy-core/{name}')
            member.size = len(data)
            member.mode = 0o755 if name == 'bin/dewy-core' else 0o644
            archive.addfile(member, io.BytesIO(data))
    checksum = output.with_name(output.name + '.sha256')
    checksum.write_text(f'{digest(output.read_bytes())}  {output.name}\n')
    return output


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('toolchain', type=Path, help='built toolchain directory containing bin/, lib/ and build.json')
    cli.add_argument('--output', type=Path, required=True, help='new .tar.gz archive')
    cli.add_argument('--revision', help='source commit, when known by the build runner')
    args = cli.parse_args()
    print(package(args.toolchain, args.output, revision=args.revision))
