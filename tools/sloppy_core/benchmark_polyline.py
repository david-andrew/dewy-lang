"""Measure joined polyline vertex generation without a window or GPU submission."""
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


def source(closed: bool) -> str:
    return f'''import p"@lib/game/draw2d.jo" as surface
from p"benchmark_harness.jo" import size_argument, clock
main=()=>{{
    let count=size_argument(args() 1000)
    let points:array<vec2>=[]
    loop i in [0..512) {{
        let p=vec2(i as float32 ((i%7)*3) as float32)
        points.push(p)
        if i%11 =? 0 points.push(p)
    }}
    let buffer:array<float32>=[] buffer.resize(512*6*9)
    let previous=surface.__b_buf
    surface.__b_buf=buffer.data() surface.__b_tex=surface.__white.id
    let checksum:int64=0
    let start=clock()
    loop iteration in [0..count) {{
        surface.__b_count=0
        polyline(points 12 WHITE closed={'true' if closed else 'false'})
        checksum+=surface.__b_count
    }}
    let elapsed=clock()-start
    surface.__b_buf=previous surface.__b_count=0
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
                          'draw2d_sha256': digest(p.parent.parent / 'lib/game/draw2d.jo')}
                      for k, p in compilers.items()},
        'workloads': {},
        'limits': ['Vertex generation only; no GPU, rasterization or window.',
                   'Point and output buffers are prepared outside the timed loop.',
                   '512 distinct points with repeated consecutive inputs, one batch per draw.',
                   'The checksum validates segment counts; geometry is checked in the test suite.',
                   'No application-wide speed claim.'],
    }
    with tempfile.TemporaryDirectory(prefix='dewy-polyline-') as directory:
        work = Path(directory)
        shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', work)
        report['harness'] = prepare_clock(work, clock)
        for closed in (False, True):
            kind = 'closed' if closed else 'open'
            program = work / f'{kind}.dewy'
            program.write_text(source(closed))
            binaries = {k: work / k for k in compilers}
            for label, compiler in compilers.items():
                run([compiler, 'build', program, '--release', '-o', binaries[label]], env)
            vertices = (512 if closed else 511) * 6
            for size in (0, 1, 17):
                for binary in binaries.values():
                    actual, _ = execute(binary, size, env)
                    if actual != vertices * size:
                        raise RuntimeError(f'{kind} count={size}: wrong vertex count {actual}')
            timings = {k: [] for k in compilers}
            labels = list(compilers)
            for sample in range(samples + 1):
                for label in labels if sample % 2 == 0 else labels[::-1]:
                    actual, timing = execute(binaries[label], count, env)
                    if actual != vertices * count:
                        raise RuntimeError(f'{kind} {label}: wrong vertex count {actual}')
                    if sample:
                        timings[label].append(timing)
            medians = {k: statistics.median(t['kernel_ns'] for t in rows) / 1e6
                       for k, rows in timings.items()}
            report['workloads'][kind] = {
                'source': program.read_text(), 'source_sha256': digest(program),
                'binary_sha256': {k: digest(p) for k, p in binaries.items()},
                'checksum': vertices * count, 'timings': timings, 'median_ms': medians,
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
    cli.add_argument('--count', type=positive, default=1000)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='thread-cpu')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    report = measure({'baseline': args.baseline.resolve(strict=True),
                      'candidate': args.compiler.resolve(strict=True)},
                     args.count, args.samples, args.clock)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
