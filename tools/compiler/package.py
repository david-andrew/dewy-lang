"""Package a built native core and its libraries for use without Python."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOSTS = {
    'linux-x86_64': ('Linux x86-64', 'dewy-core', 'my-game-native', 'Linux'),
    'windows': ('Windows x64', 'dewy-core.exe', 'my-game-native.exe', 'Windows'),
    'macos': ('macOS ARM64', 'dewy-core', 'my-game-native', 'macOS'),
    'linux-arm64': ('Linux ARM64', 'dewy-core', 'my-game-native', 'Linux'),
}
# Compiler host -> release platform (the dewy-core-<platform>.tar.gz asset name).
PLATFORMS = {'linux-x86_64': 'linux-x86_64', 'windows': 'windows-x86_64',
             'macos': 'macos-arm64', 'linux-arm64': 'linux-arm64'}

README = """Dewy compact core — development toolchain for {title}

Keep bin/ and lib/ together; the compiler finds its libraries beside itself.
The extracted directory can be moved. Running the compiler requires neither
Python nor a C compiler.

From this directory:
  ./bin/{binary} --version
  ./bin/{binary} new my-game
  ./bin/{binary} build my-game/main.dewy -o {native}
  ./bin/{binary} build my-game/main.dewy --target wasm32 -o my-game-web
  ./bin/{binary} watch my-game/main.dewy

Open my-game-web.html in a browser, or run ./{native} on a {desktop} desktop.
The compiler also accepts ordinary .dewy programs and an interactive `repl`.
Use an absolute path to bin/{binary} when working from another directory.

This is the experimental compact core. Language and platform coverage:
https://github.com/david-andrew/dewy-lang/blob/master/docs/DEVELOPMENT.md

PACKAGE.json records the payload hashes and an optional source revision;
RELEASE repeats the platform and revision as plain text for installers.
{provenance} records the compiler build and source provenance.
"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_identity(platform: str, revision: str | None) -> str:
    """The plain-text identity installers check without a JSON parser."""
    version = (ROOT / 'VERSION').read_text().strip()
    return (f'dewy-toolchain-release 1\nversion {version}\nplatform {platform}\n'
            f'revision {revision or "unknown"}\n')


def package(toolchain: Path, output: Path, *, revision: str | None = None) -> Path:
    toolchain = toolchain.resolve(strict=True)
    host = 'linux-x86_64'
    provenance = 'build.json'
    if (toolchain / 'HOST_BUILD.json').is_file():
        provenance = 'HOST_BUILD.json'
        cross = json.loads((toolchain / provenance).read_text())
        host = cross['host']
        if host not in HOSTS:
            raise ValueError(f'unsupported compiler host: {host}')
        manifest = cross['source_build']
        compiler_hash = cross['compiler_sha256']
    else:
        manifest = json.loads((toolchain / provenance).read_text())
        compiler_hash = manifest['core_sha256']
    title, binary, native, desktop = HOSTS[host]
    executable = f'bin/{binary}'
    expected = {executable: compiler_hash}
    expected.update({name: sha for name, sha in manifest['sources_sha256'].items()
                     if name.startswith('lib/')})
    expected['LICENSE'] = manifest['sources_sha256']['LICENSE']
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
    payload[provenance] = (toolchain / provenance).read_bytes()
    payload['README.txt'] = README.format(title=title, binary=binary, native=native,
                                         desktop=desktop, provenance=provenance).encode()
    payload['RELEASE'] = release_identity(PLATFORMS[host], revision).encode()
    metadata = {'format': 1, 'host': host, 'revision': revision,
                'files': {name: digest(data) for name, data in payload.items()}}
    payload['PACKAGE.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids replacing an earlier artifact accidentally.
    with output.open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, data in sorted(payload.items()):
            member = tarfile.TarInfo(f'dewy-core/{name}')
            member.size = len(data)
            member.mode = 0o755 if name == executable else 0o644
            archive.addfile(member, io.BytesIO(data))
    checksum = output.with_name(output.name + '.sha256')
    checksum.write_text(f'{digest(output.read_bytes())}  {output.name}\n')
    return output


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('toolchain', type=Path, help='built toolchain with bin/, lib/ and build.json or HOST_BUILD.json')
    cli.add_argument('--output', type=Path, required=True, help='new .tar.gz archive')
    cli.add_argument('--revision', help='source commit, when known by the build runner')
    args = cli.parse_args()
    print(package(args.toolchain, args.output, revision=args.revision))
