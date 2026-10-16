"""Compile checked Dewy through the experimental Sloppy x86-64 emitter.

Use as `python -m tools.sloppy_bridge.run SOURCE --dewy COMPILER
--emitter EMITTER --output NEW_DIRECTORY [--release]` from the repo root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from udewy.cache import cache_artifact
from udewy.stream import Stream

from .adapter import Adapter

ROOT = Path(__file__).resolve().parents[2]


def compile_program(source: Path, compiler: Path, emitter: Path, work: Path, *, release=False):
    source, compiler, emitter, work = (p.resolve(strict=True) for p in (source, compiler, emitter, work))
    ir_file, binary = work / 'program.ir', work / 'program'
    stream_path = work / cache_artifact(source, '.ubc', cwd=work)
    if ir_file.exists() or binary.exists() or stream_path.exists():
        raise FileExistsError('bridge output already exists')
    noop = shutil.which('true')
    if noop is None: raise RuntimeError('the deferred backend handoff requires true')
    env = {**os.environ, 'DEWY_LIBRARY_ROOT': str(ROOT / 'library'), 'DEWY_EMIT': 'bytecode',
           'DEWY_UDEWY': noop, 'DEWY_FAILURE_LOG': '0'}
    command = [str(compiler), '--timings', '-c', '--target', 'x86_64', str(source)]
    start = time.perf_counter()
    result = subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, timeout=180, check=False)
    frontend = time.perf_counter()
    (work / 'frontend.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'Dewy rejected the program:\n{result.stdout}{result.stderr}')
    if not stream_path.is_file(): raise RuntimeError('Dewy did not emit a checked stream')
    stream = Stream(stream_path.read_bytes())
    if stream.link_artifacts: raise ValueError('Sloppy bridge: link artifacts are unsupported')
    ir_file.write_bytes(stream.play(Adapter()))
    adapted = time.perf_counter()
    emission = [str(emitter), str(ir_file), str(binary), 'release' if release else 'debug']
    generated = subprocess.run(emission, capture_output=True, text=True, timeout=180, check=False)
    (work / 'emitter.log').write_text(generated.stdout + generated.stderr)
    if generated.returncode or not binary.is_file():
        binary.unlink(missing_ok=True)
        raise RuntimeError(f'Sloppy emission failed:\n{generated.stdout}{generated.stderr}')
    finished = time.perf_counter()
    measurement = {'source': str(source), 'command': command, 'emission': emission,
                   'frontend_lower_stream_s': frontend - start, 'adapt_s': adapted - frontend,
                   'codegen_s': finished - adapted, 'total_s': finished - start,
                   'stream_bytes': stream_path.stat().st_size, 'ir_bytes': ir_file.stat().st_size,
                   'binary_bytes': binary.stat().st_size,
                   'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                   'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
                   'emitter_sha256': hashlib.sha256(emitter.read_bytes()).hexdigest()}
    (work / 'measurement.json').write_text(json.dumps(measurement, indent=2) + '\n')
    return binary, measurement


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--dewy', type=Path, required=True)
    parser.add_argument('--emitter', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    binary, measurement = compile_program(args.source, args.dewy, args.emitter, args.output, release=args.release)
    print(json.dumps(measurement, indent=2))
