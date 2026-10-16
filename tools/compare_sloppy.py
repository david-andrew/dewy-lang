#!/usr/bin/env python3
"""Compare identical particle workloads in Dewy, Sloppy debug/release and C.

Every compilation uses a fresh directory, including a fresh Dewy prelude cache.
OS file caches are not flushed. Compiler bootstrap time is not included. The
JSON records all samples, tool identities and checkout state; checksums must
agree for every input and repetition before a result is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'dewy/benchmarks/apps'


def file_identity(path: Path) -> dict:
    path = path.resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checkout(root: Path) -> dict:
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    return {'path': str(root), 'revision': git('rev-parse', 'HEAD'),
            'status': git('status', '--porcelain')}


def invoke(command: list[str], work: Path, env: dict, timeout: float) -> dict:
    rss = work / 'peak-rss.txt'
    started = time.perf_counter()
    process = subprocess.Popen(['/usr/bin/time', '-f', '%M', '-o', str(rss), *command],
                               cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    elapsed = time.perf_counter() - started
    if process.returncode:
        raise RuntimeError(f'{command} exited {process.returncode}\n{stdout}{stderr}')
    return {'command': command, 'wall_seconds': elapsed, 'peak_rss_kib': int(rss.read_text()),
            'stdout': stdout, 'stderr': stderr}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dewy', type=Path, required=True, help='native Dewy executable')
    parser.add_argument('--udewy', type=Path, help='defaults to udewy beside --dewy')
    parser.add_argument('--sloppy-root', type=Path, required=True)
    parser.add_argument('--sloppy-emitter', type=Path, help='also measure the checked Dewy → Sloppy IR bridge')
    parser.add_argument('--source-core', type=Path, help='also build Dewy syntax through the compact Sloppy core')
    parser.add_argument('--dense-records', action='store_true',
                        help='also measure the opt-in dense Dewy representation on each Dewy backend')
    parser.add_argument('--output', type=Path, required=True, help='new JSON result file')
    parser.add_argument('--dewy-source', type=Path, default=SOURCES / 'records.dewy',
                        help='Dewy variant implementing the same particle workload/checksums')
    parser.add_argument('--builds', type=int, default=3)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--sizes', type=int, nargs='+', default=[0, 1, 10, 100_000, 1_000_000])
    parser.add_argument('--modes', nargs='+', help='measure only these mode names (default: all enabled modes)')
    args = parser.parse_args()
    if args.builds < 1 or args.runs < 1 or any(n < 0 or n > 1_000_000_000 for n in args.sizes):
        parser.error('builds/runs must be positive; sizes must be in 0..1000000000')
    if args.output.exists():
        parser.error('use a new output path to preserve earlier results')
    dewy = args.dewy.resolve(strict=True)
    dewy_source = args.dewy_source.resolve(strict=True)
    udewy = (args.udewy or dewy.with_name('udewy')).resolve(strict=True)
    sloppy_root = args.sloppy_root.resolve(strict=True)
    sloppy = sloppy_root / 'bin/sloppy'
    cc = Path(shutil.which('cc') or '/missing/cc')
    # Do not let a shell's tuning/route/library overrides silently change the run.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_UDEWY=str(udewy), DEWY_LIBRARY_ROOT=str(ROOT / 'library'), DEWY_EMIT='native',
               DEWY_FAILURE_LOG='0', SLOPPY_LIB=str(sloppy_root / 'lib'), SLOPPY_EMIT_WORKERS='1')
    result = {
        'machine': platform.platform(),
        'cpu': next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                     if line.startswith('model name')), platform.machine()),
        'cache': 'fresh build directory and prelude per compilation; OS caches not flushed',
        'dewy_checkout': checkout(ROOT), 'sloppy_checkout': checkout(sloppy_root),
        'tools': {name: file_identity(path) for name, path in
                  [('dewy', dewy), ('udewy', udewy), ('sloppy', sloppy), ('cc', cc)]},
        'sources': [file_identity(dewy_source), *[file_identity(SOURCES / name) for name in
                    ['records.jo', 'records.c', 'harness.dewy', 'harness.h']]],
        'builds': {}, 'runs': {},
    }
    modes = ['C', 'sloppy-debug', 'sloppy-release', 'dewy-native']
    if args.sloppy_emitter:
        emitter = args.sloppy_emitter.resolve(strict=True)
        result['tools']['sloppy-emitter'] = file_identity(emitter)
        manifest = emitter.parent / 'build.json'
        if manifest.is_file(): result['emitter_build'] = json.loads(manifest.read_text())
        modes.extend(['dewy-sloppy-debug', 'dewy-sloppy-release'])
        env['PYTHONPATH'] = str(ROOT)
    if args.dense_records:
        modes.extend(mode.replace('dewy-', 'dewy-dense-', 1) for mode in modes.copy()
                     if mode.startswith('dewy-'))
    if args.source_core:
        core = args.source_core.resolve(strict=True)
        result['tools']['source-core'] = file_identity(core)
        result['core_build'] = json.loads((core.parent.parent / 'build.json').read_text())
        result['sources'].append(file_identity(ROOT / 'tools/sloppy_core/benchmark_harness.jo'))
        result['core_source_change'] = 'only harness.dewy import replaced with benchmark_harness.jo; original algorithm unchanged'
        modes.extend(['core-debug', 'core-release'])
    if args.modes:
        unavailable = set(args.modes) - set(modes)
        if unavailable:
            parser.error(f'modes unavailable with these options: {sorted(unavailable)}; available: {modes}')
        modes = list(dict.fromkeys(args.modes))
    checksums: dict[int, str] = {}
    with tempfile.TemporaryDirectory(prefix='dewy-sloppy-') as scratch:
        for mode in modes:
            backend_mode = mode.replace('dewy-dense-', 'dewy-', 1)
            mode_env = {**env, 'DEWY_DENSE_RECORDS': '1' if mode.startswith('dewy-dense-') else '0'}
            builds = result['builds'][mode] = []
            runs = result['runs'][mode] = []
            for sample in range(args.builds):
                work = Path(scratch) / f'{mode}-{sample}'
                work.mkdir()
                mode_env['DEWY_PRELUDE_CACHE_DIR'] = str(work / '__dewycache__/prelude')
                binary = work / 'records'
                if mode == 'C':
                    command = [str(cc), '-O2', str(SOURCES / 'records.c'), '-o', str(binary)]
                elif mode.startswith('sloppy'):
                    command = [str(sloppy), 'build', str(SOURCES / 'records.jo'), '-o', str(binary)]
                    if mode == 'sloppy-release':
                        command.append('--release')
                elif mode.startswith('core-'):
                    mode_env['SLOPPY_LIB'] = str(core.parent.parent / 'lib')
                    original = dewy_source.read_text()
                    assert original.count('p"harness.dewy"') == 1
                    source = work / dewy_source.name
                    source.write_text(original.replace('p"harness.dewy"', 'p"benchmark_harness.jo"'))
                    shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', work)
                    command = [str(core), 'build', str(source), '--time', '-o', str(binary)]
                    if mode == 'core-release': command.append('--release')
                elif backend_mode.startswith('dewy-sloppy'):
                    bridge_work = work / 'bridge'
                    binary = bridge_work / 'program'
                    command = [sys.executable, '-m', 'tools.sloppy_bridge.run', str(dewy_source),
                               '--dewy', str(dewy), '--emitter', str(emitter), '--output', str(bridge_work)]
                    if mode.endswith('release'): command.append('--release')
                else:
                    # Mirror the CLI's documented artifact layout for an external source.
                    from udewy.cache import cache_artifact
                    binary = work / cache_artifact(dewy_source, cwd=work)
                    command = [str(dewy), '--timings', '-c', str(dewy_source)]
                built = invoke(command, work, mode_env, 180)
                built['dense_records'] = mode_env['DEWY_DENSE_RECORDS'] == '1'
                if backend_mode.startswith('dewy-sloppy'):
                    built['stages'] = json.loads((bridge_work / 'measurement.json').read_text())
                    built['frontend_log'] = (bridge_work / 'frontend.log').read_text()
                if backend_mode == 'dewy-native' and 'native route:' in built['stdout']:
                    raise RuntimeError(f'Dewy fell back from native emission: {built["stdout"]}')
                builds.append(built)
                # Execute every build, not only the last one. All modes and inputs
                # must agree, including zero/one-element edge cases.
                for size in args.sizes:
                    for repeat in range(args.runs):
                        run = invoke([str(binary), str(size)], work, mode_env, 60)
                        fields = run['stdout'].split()
                        if len(fields) != 2 or not all(field.isdecimal() for field in fields):
                            raise RuntimeError(f'{mode}: invalid benchmark output: {run["stdout"]!r}')
                        checksum, ns = fields
                        if checksums.setdefault(size, checksum) != checksum:
                            raise RuntimeError(f'{mode}, size {size}: checksum {checksum} != {checksums[size]}')
                        runs.append(dict(run, build=sample, repeat=repeat, size=size,
                                         checksum=checksum, kernel_ns=int(ns)))
            print(f'{mode}: cold compile median {statistics.median(b["wall_seconds"] for b in builds):.4f}s', flush=True)
            for size in args.sizes:
                ns = [r['kernel_ns'] for r in runs if r['size'] == size]
                print(f'  {size}: kernel median {statistics.median(ns) / 1e6:.3f}ms; checksum {checksums[size]}', flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')


if __name__ == '__main__':
    # tools/ is not a package; allow importing the repository's cache layout.
    sys.path.insert(0, str(ROOT))
    main()
