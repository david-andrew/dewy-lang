"""Build the experiment from pinned source, never modifying the Sloppy checkout."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

PIN = '235e19a271bccad3fe72e36d03264807a632dc1b'
HERE = Path(__file__).resolve().parent

# This is the only change made to the pinned backend. µDewy alloca allocates
# afresh every time; Sloppy's fixed frame slots are not equivalent. Its frame
# accesses/restoration use rbp, so an aligned rsp adjustment composes with calls.
ALLOCA_ANCHOR = '        intr:\n            if ins.imm == 1:\n'
ALLOCA_PATCH = '''        intr:
            if ins.imm == 1000:
                ld(RAX, int(ir.args[a]))
                b(0x48); b(0x83); b(0xC0); b(15)  # add rax, 15
                b(0x48); b(0x83); b(0xE0); b(0xF0) # and rax, -16
                b(0x48); b(0x29); b(0xC4)         # sub rsp, rax
                mov_rr(RAX, RSP)
                st(d, RAX)
            else if ins.imm == 1:
'''


def build(root: Path, output: Path) -> Path:
    root, output = root.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    archive = subprocess.check_output(['git', '-C', str(root), 'archive', PIN,
                                       'compiler', 'lib', 'LICENSE'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(output, filter='data')
    source = output / 'compiler/x64.jo'
    text = source.read_text()
    if text.count(ALLOCA_ANCHOR) != 1: raise ValueError('pinned alloca patch anchor mismatch')
    source.write_text(text.replace(ALLOCA_ANCHOR, ALLOCA_PATCH))
    (output / 'emit.jo').write_bytes((HERE / 'emit.jo').read_bytes())
    binary = output / 'dewy-sloppy-emit'
    seed = root / 'bin/sloppy'
    subprocess.run([str(seed), 'build', str(output / 'emit.jo'), '--release', '-o', str(binary)],
                   env={**os.environ, 'SLOPPY_LIB': str(output / 'lib'), 'SLOPPY_EMIT_WORKERS': '1'},
                   check=True, timeout=180)
    manifest = {'sloppy_revision': PIN, 'seed_sha256': hashlib.sha256(seed.read_bytes()).hexdigest(),
                'emitter_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'driver_sha256': hashlib.sha256((HERE / 'emit.jo').read_bytes()).hexdigest(),
                'patched_backend_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    (output / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return binary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sloppy-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new, dedicated build directory')
    args = parser.parse_args()
    print(build(args.sloppy_root, args.output))
