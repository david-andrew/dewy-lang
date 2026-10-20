"""Measure dictionary iteration over dense and partially removed entry arrays."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

from tools.compiler.benchmark_apps import ROOT, digest, execute, prepare_clock, run
from tools.compiler.benchmark_compile import positive

KINDS = ('pairs', 'counted', 'zip', 'first')


def source(kind: str, sparse: bool) -> str:
    body = {
        'pairs': 'loop [key value] in values {checksum+=key+value[0]}',
        'counted': 'loop i in 0.. and key in values {checksum+=i+key}',
        'zip': 'loop [key value] in values and i in [0..8192) {checksum+=key+value[0]+i}',
        'first': 'loop [key value] in values {checksum+=key+value[0] break}',
    }[kind]
    removal = 'loop i in [0,4..8192) {values.remove(i)}' if sparse else ''
    return f'''from p"benchmark_harness.jo" import size_argument, clock
main=()=>{{
    let count=size_argument(args() 1000)
    let values:dict<int64 array<int64>>=[]
    values.reserve(8192)
    loop i in [0..8192) {{values[i]=[i*3+1 i]}}
    {removal}
    let checksum:int64=0
    let start=clock()
    loop iteration in [0..count) {{{body}}}
    let elapsed=clock()-start
    printl("{{checksum}} {{elapsed}}")
}}'''


def expected(kind: str, sparse: bool, count: int) -> int:
    live = [i for i in range(8192) if not sparse or i % 4]
    if kind == 'first':
        return (live[0] * 4 + 1) * count
    return sum(i + key if kind == 'counted' else key * 4 + 1 + (i if kind == 'zip' else 0)
               for i, key in enumerate(live)) * count


def measure(compilers: dict[str, Path], count: int, samples: int, clock: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'platform': platform.platform(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'cpu_affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        'load_average_start': os.getloadavg(),
        'count': count, 'samples': samples, 'warmups': 1, 'clock': clock,
        'flags': ['--release'],
        'compilers': {k: {'path': str(p), 'sha256': digest(p)} for k, p in compilers.items()},
        'workloads': {},
        'limits': ['Map construction/removal is outside the timed kernel.',
                   'Sparse maps retain 25% tombstones; values are two-element integer arrays.',
                   'Repeated full traversals and early exits; not overall application performance.'],
    }
    with tempfile.TemporaryDirectory(prefix='dewy-iteration-') as directory:
        work = Path(directory)
        shutil.copy2(ROOT / 'tools/compiler/benchmark_harness.jo', work)
        report['harness'] = prepare_clock(work, clock)
        for sparse in (False, True):
            for kind in KINDS:
                name = kind + ('-sparse' if sparse else '-dense')
                program = work / f'{name}.dewy'
                program.write_text(source(kind, sparse))
                binaries = {k: work / k for k in compilers}
                for label, compiler in compilers.items():
                    run([compiler, 'build', program, '--release', '-o', binaries[label]], env)
                for size in (0, 1, 17):
                    for binary in binaries.values():
                        actual, _ = execute(binary, size, env)
                        if actual != expected(kind, sparse, size):
                            raise RuntimeError(f'{name} count={size}: wrong checksum {actual}')
                timings = {k: [] for k in compilers}
                labels = list(compilers)
                for sample in range(samples + 1):
                    for label in labels if sample % 2 == 0 else labels[::-1]:
                        actual, timing = execute(binaries[label], count, env)
                        if actual != expected(kind, sparse, count):
                            raise RuntimeError(f'{name} {label}: wrong checksum {actual}')
                        if sample:
                            timings[label].append(timing)
                medians = {k: statistics.median(t['kernel_ns'] for t in rows) / 1e6
                           for k, rows in timings.items()}
                report['workloads'][name] = {
                    'source': program.read_text(), 'source_sha256': digest(program),
                    'binary_sha256': {k: digest(p) for k, p in binaries.items()},
                    'checksum': expected(kind, sparse, count), 'timings': timings, 'median_ms': medians,
                    'paired_kernel_ratio': statistics.median(
                        c['kernel_ns'] / b['kernel_ns']
                        for b, c in zip(timings['baseline'], timings['candidate'])),
                }
                print(f'{name}: {medians}', flush=True)
    report['load_average_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path, required=True)
    cli.add_argument('--count', type=positive, default=1000)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='thread-cpu')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    report = measure({'baseline': args.baseline.resolve(strict=True),
                      'candidate': args.compiler.resolve(strict=True)},
                     args.count, args.samples, args.clock)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
