"""Compare explicit inline graph neighbors with growable arrays and the C graph."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import tempfile
from pathlib import Path

from tools.sloppy_core.benchmark_apps import (
    APPS,
    CHECKSUMS_1000,
    digest,
    execute,
    prepare_clock,
    prepare_source,
    run,
)
from tools.sloppy_core.benchmark_compile import positive


def inline_source(source: str) -> str:
    # Keep the graph, traversal and checksums unchanged. Only its known four
    # neighbors move from individual growable arrays into dictionary values.
    source = source.replace('dict<int64 array<int64>>', 'dict<int64 array<int64 length=DEGREE>>')
    old = 'let targets:array<int64>=[label((i+1)%count)]'
    new = 'let targets:array<int64 length=DEGREE>=[0 0 0 0]\n        targets[0]=label((i+1)%count)'
    if source.count(old) != 1 or source.count('targets.push(label(seed%count))') != 1:
        raise RuntimeError('Graph source changed; update the inline-storage variant')
    return source.replace(old, new).replace('targets.push(label(seed%count))', 'targets[j]=label(seed%count)')


def measure(compiler: Path, count: int, samples: int, clock: str, cc: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'platform': platform.platform(),
        'cpu_affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        'load_average_start': os.getloadavg(),
        'count': count, 'samples': samples, 'warmups': 1, 'clock': clock,
        'compiler': {'path': str(compiler), 'sha256': digest(compiler)},
        'cc': run([cc, '--version'], env)[0],
        'core_flags': ['--release'], 'c_flags': ['-O2'],
        'limits': ['Explicit source representation choice; the compiler does not infer fixed storage here.',
                   'Graph construction is outside the timed BFS kernel.',
                   'The C reference uses a custom hash table and one flat neighbor allocation.',
                   'Growable arrays remain the default; this is not a speedup to the original source.'],
    }
    with tempfile.TemporaryDirectory(prefix='dewy-fixed-graph-') as directory:
        work = Path(directory)
        dynamic = prepare_source('graph', work)
        report['harness'] = prepare_clock(work, clock)
        inline = work / 'inline.dewy'
        inline.write_text(inline_source(dynamic.read_text()))
        c_source = work / 'graph.c'
        shutil.copy2(APPS / 'graph.c', c_source)
        sources = {'dynamic': dynamic, 'inline': inline, 'c': c_source}
        binaries = {label: work / label for label in sources}
        builds = {}
        for label in ('dynamic', 'inline'):
            _, builds[label] = run([compiler, 'build', sources[label], '--release', '-o', binaries[label]], env)
        _, builds['c'] = run([cc, '-O2', c_source, '-o', binaries['c']], env)
        checksums = {}
        for size in (0, 1, 17, 1000):
            checks = {label: execute(binary, size, env)[0] for label, binary in binaries.items()}
            if len(set(checks.values())) != 1 or size == 1000 and checks['c'] != CHECKSUMS_1000['graph']:
                raise RuntimeError(f'count={size}: wrong checksums {checks}')
            checksums[str(size)] = checks['c']
        timings = {label: [] for label in sources}
        labels = list(sources)
        checksum = None
        for sample in range(samples + 1):
            order = labels[sample % len(labels):] + labels[:sample % len(labels)]
            if sample % 2: order = order[::-1]
            for label in order:
                actual, timing = execute(binaries[label], count, env)
                if checksum is None: checksum = actual
                if actual != checksum: raise RuntimeError(f'{label}: wrong checksum {actual}, expected {checksum}')
                if sample: timings[label].append(timing)
        report.update(
            sources={label: {'text': path.read_text(), 'sha256': digest(path)} for label, path in sources.items()},
            binary_sha256={label: digest(path) for label, path in binaries.items()},
            build_seconds=builds, preflight_checksums=checksums, checksum=checksum,
            timings=timings,
            median_kernel_ms={label: statistics.median(row['kernel_ns'] for row in rows) / 1e6
                              for label, rows in timings.items()},
            paired_inline_dynamic_ratio=statistics.median(
                fixed['kernel_ns'] / dynamic['kernel_ns']
                for fixed, dynamic in zip(timings['inline'], timings['dynamic'])),
        )
    report['load_average_end'] = os.getloadavg()
    print(report['median_kernel_ms'], flush=True)
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--count', type=positive, default=1_000_000)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='thread-cpu')
    cli.add_argument('--cc', default='cc')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    report = measure(args.compiler.resolve(strict=True), args.count, args.samples, args.clock, args.cc)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
