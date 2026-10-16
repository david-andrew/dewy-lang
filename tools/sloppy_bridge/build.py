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

# This is the extension made to the pinned backend. µDewy alloca allocates
# afresh every time; Sloppy's fixed frame slots are not equivalent. Its frame
# accesses/restoration use rbp, so an aligned rsp adjustment composes with calls.
ALLOCA_ANCHOR = '        intr:\n            if ins.imm == 1:\n'
CALL_ANCHOR = '    if op == .intr and ins.imm >= 2: return true\n'
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


def build(root: Path, output: Path, *, bootstrap=False) -> Path:
    root, output = root.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    archive = subprocess.check_output(['git', '-C', str(root), 'archive', PIN,
                                       'compiler', 'lib', 'stage0', 'LICENSE'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(output, filter='data')
    env = {**os.environ, 'SLOPPY_LIB': str(output / 'lib'), 'SLOPPY_EMIT_WORKERS': '1'}
    seed = root / 'bin/sloppy'
    bootstrap_hashes = []
    if bootstrap:
        # All three generations use pristine pinned source. Patch the backend
        # only afterwards; neither an installed Sloppy nor its dirty tree is used.
        subprocess.run(['make', '-s', '-C', str(output / 'stage0')], check=True, timeout=180)
        seed = output / 'stage0/sloppy0'
        for generation in range(1, 4):
            next_seed = output / f'sloppy{generation}'
            command = [str(seed), *([] if generation == 1 else ['build']),
                       str(output / 'compiler/main.jo'), '-o', str(next_seed)]
            subprocess.run(command, env=env, cwd=output, check=True, timeout=180)
            seed = next_seed
            bootstrap_hashes.append(hashlib.sha256(seed.read_bytes()).hexdigest())
        if bootstrap_hashes[1] != bootstrap_hashes[2]:
            raise RuntimeError('pinned Sloppy bootstrap did not reach a binary fixed point')
    source = output / 'compiler/x64.jo'
    text = source.read_text()
    if text.count(ALLOCA_ANCHOR) != 1: raise ValueError('pinned alloca patch anchor mismatch')
    if text.count(CALL_ANCHOR) != 1: raise ValueError('pinned alloca clobber anchor mismatch')
    # RAX is reserved scratch in both Sloppy allocators. The extension changes
    # only RAX/RSP/flags, so saving caller-saved values as for a call is needless.
    text = text.replace(CALL_ANCHOR, '    if op == .intr and ins.imm == 1000: return false\n' + CALL_ANCHOR)
    source.write_text(text.replace(ALLOCA_ANCHOR, ALLOCA_PATCH))
    # Reuse the pinned compiler's dependency ordering without importing its CLI
    # or running its frontend. Its MIT notice is retained in the build root.
    main = (output / 'compiler/main.jo').read_text()
    order = main[main.index('callee_order = '):main.index('\ncompile = ')]
    (output / 'order.jo').write_text("use 'compiler/ir.jo'\nuse 'compiler/inline.jo'\n\n" + order)
    (output / 'emit.jo').write_bytes((HERE / 'emit.jo').read_bytes())
    binary = output / 'dewy-sloppy-emit'
    subprocess.run([str(seed), 'build', str(output / 'emit.jo'), '--release', '-o', str(binary)],
                   env=env, check=True, timeout=180)
    manifest = {'sloppy_revision': PIN, 'seed_sha256': hashlib.sha256(seed.read_bytes()).hexdigest(),
                'bootstrap_generations_sha256': bootstrap_hashes,
                'emitter_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'driver_sha256': hashlib.sha256((HERE / 'emit.jo').read_bytes()).hexdigest(),
                'patched_backend_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    (output / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return binary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sloppy-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new, dedicated build directory')
    parser.add_argument('--bootstrap', action='store_true', help='build pinned C seed and verify the Sloppy fixed point')
    args = parser.parse_args()
    print(build(args.sloppy_root, args.output, bootstrap=args.bootstrap))
