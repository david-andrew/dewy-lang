"""Measure unchanged inline-array selections against a previous toolchain."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import tempfile
from pathlib import Path

from tools.sloppy_core.benchmark_apps import ROOT, digest, execute, prepare_clock, run
from tools.sloppy_core.benchmark_compile import positive

SELECTIONS = {
    'stepped': ('1,17..', list(range(1, 512, 16))),
    'indexed': ('indexes', [1, 100, 300, 511]),
}


def source(selection: str) -> str:
    return f'''from p"benchmark_harness.jo" import size_argument, clock
main=()=>{{
    let count=size_argument(args() 20000)
    let values:array<int64 length=512>=[]
    loop i in [0..512) {{values[i]=i}}
    let indexes=[1 100 300 511]
    let checksum:int64=0
    let start=clock()
    loop iteration in [0..count) {{
        let chosen=values[{selection}]
        loop value in chosen {{checksum+=value}}
    }}
    let elapsed=clock()-start
    printl("{{checksum}} {{elapsed}}")
}}'''


def measure(compilers: dict[str, Path], count: int, samples: int, clock: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'platform': platform.platform(),
        'cpu_affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        'load_average_start': os.getloadavg(),
        'count': count, 'samples': samples, 'warmups': 1, 'clock': clock,
        'flags': ['--release'],
        'compilers': {k: {'path': str(p), 'sha256': digest(p),
                          'array_sha256': digest(p.parent.parent / 'lib/core/array.jo'),
                          'ranges_sha256': digest(p.parent.parent / 'lib/std/dewy_ranges.jo')}
                      for k, p in compilers.items()},
        'workloads': {},
        'limits': ['Same source and fixed-size representation for both toolchains.',
                   'Input construction is outside timing; selection allocation and summation are timed.',
                   'Isolated selection workloads; no application-wide speed claim.'],
    }
    with tempfile.TemporaryDirectory(prefix='dewy-fixed-selection-') as directory:
        work = Path(directory)
        shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', work)
        report['harness'] = prepare_clock(work, clock)
        for kind, (selection, indexes) in SELECTIONS.items():
            program = work / f'{kind}.dewy'
            program.write_text(source(selection))
            binaries = {k: work / k for k in compilers}
            builds = {}
            for label, compiler in compilers.items():
                _, builds[label] = run([compiler, 'build', program, '--release', '-o', binaries[label]], env)
            expected = sum(indexes)
            for size in (0, 1, 17):
                for binary in binaries.values():
                    actual, _ = execute(binary, size, env)
                    if actual != expected * size:
                        raise RuntimeError(f'{kind} count={size}: wrong checksum {actual}')
            timings = {k: [] for k in compilers}
            labels = list(compilers)
            for sample in range(samples + 1):
                for label in labels if sample % 2 == 0 else labels[::-1]:
                    actual, timing = execute(binaries[label], count, env)
                    if actual != expected * count:
                        raise RuntimeError(f'{kind} {label}: wrong checksum {actual}')
                    if sample:
                        timings[label].append(timing)
            medians = {k: statistics.median(t['kernel_ns'] for t in rows) / 1e6
                       for k, rows in timings.items()}
            report['workloads'][kind] = {
                'source': program.read_text(), 'source_sha256': digest(program),
                'binary_sha256': {k: digest(p) for k, p in binaries.items()},
                'build_seconds': builds, 'checksum': expected * count,
                'timings': timings, 'median_ms': medians,
                'paired_candidate_baseline_ratio': statistics.median(
                    c['kernel_ns'] / b['kernel_ns']
                    for b, c in zip(timings['baseline'], timings['candidate'])),
            }
            print(f'{kind}: {medians}', flush=True)
    report['load_average_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path, required=True)
    cli.add_argument('--count', type=positive, default=20_000)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='thread-cpu')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    report = measure({'baseline': args.baseline.resolve(strict=True),
                      'candidate': args.compiler.resolve(strict=True)},
                     args.count, args.samples, args.clock)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
