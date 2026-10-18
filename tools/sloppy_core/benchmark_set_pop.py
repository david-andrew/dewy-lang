"""Compare draining sets of scalar and managed keys after arbitrary removals."""
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

from tools.sloppy_core.benchmark_apps import ROOT, digest, execute, prepare_clock, run
from tools.sloppy_core.benchmark_compile import positive


def source(managed: bool) -> str:
    member = '[i i*3+1]' if managed else 'i'
    score = 'value[0]+value[1]' if managed else 'value*4+1'
    return f'''from p"benchmark_harness.jo" import size_argument, clock
main=()=>{{
    let count=size_argument(args() 4096)
    let values=set[loop i in [0..count) {member}]
    loop i in [0,4..count) {{values.remove({member})}}
    let checksum:int64=0 let rank:int64=1
    let start=clock()
    loop not values.is_empty() {{
        let value=values.pop()
        checksum+=({score})*rank
        rank+=1
    }}
    let elapsed=clock()-start
    printl("{{checksum}} {{elapsed}}")
}}'''


def expected(count: int) -> int:
    return sum((value * 4 + 1) * rank
               for rank, value in enumerate(reversed([i for i in range(count) if i % 4]), 1))


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
        'compilers': {k: {'path': str(p), 'sha256': digest(p),
                          'set_library_sha256': digest(p.parent.parent / 'lib/std/dewy_sets.jo')}
                      for k, p in compilers.items()},
        'workloads': {},
        'limits': ['Construction and removal of every fourth member are outside the timed kernel.',
                   'The timed loop drains the set; checksums also verify reverse insertion order.',
                   'Scalar integers and two-integer arrays; not overall application performance.'],
    }
    with tempfile.TemporaryDirectory(prefix='dewy-set-pop-') as directory:
        work = Path(directory)
        shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', work)
        report['harness'] = prepare_clock(work, clock)
        for managed in (False, True):
            name = 'managed' if managed else 'scalar'
            program = work / f'{name}.dewy'
            program.write_text(source(managed))
            binaries = {k: work / k for k in compilers}
            for label, compiler in compilers.items():
                run([compiler, 'build', program, '--release', '-o', binaries[label]], env)
            for size in (0, 1, 2, 17, 1000):
                for binary in binaries.values():
                    actual, _ = execute(binary, size, env)
                    if actual != expected(size):
                        raise RuntimeError(f'{name} count={size}: wrong checksum {actual}')
            timings = {k: [] for k in compilers}
            labels = list(compilers)
            for sample in range(samples + 1):
                for label in labels if sample % 2 == 0 else labels[::-1]:
                    actual, timing = execute(binaries[label], count, env)
                    if actual != expected(count):
                        raise RuntimeError(f'{name} {label}: wrong checksum {actual}')
                    if sample:
                        timings[label].append(timing)
            medians = {k: statistics.median(t['kernel_ns'] for t in rows) / 1e6
                       for k, rows in timings.items()}
            report['workloads'][name] = {
                'source': program.read_text(), 'source_sha256': digest(program),
                'binary_sha256': {k: digest(p) for k, p in binaries.items()},
                'checksum': expected(count), 'timings': timings, 'median_ms': medians,
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
    cli.add_argument('--count', type=positive, default=4096)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='thread-cpu')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    report = measure({'baseline': args.baseline.resolve(strict=True),
                      'candidate': args.compiler.resolve(strict=True)},
                     args.count, args.samples, args.clock)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
