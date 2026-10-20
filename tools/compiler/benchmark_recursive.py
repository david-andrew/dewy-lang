"""Compare Dewy recursive value traversal with ordinary C pointer traversal.

These workloads are separate from the fixed historical gate, whose compiler
predates recursive records. Construction and destruction are outside the timer.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from tools.compiler import benchmark_apps
from tools.compiler.performance_gate import compare_samples, save_report, toolchain_identity

COUNTS = {'recursive_tree': 2000000, 'recursive_list': 20000}


def checksum(name: str, count: int) -> int:
    if name == 'recursive_tree':
        period = [((i * 73) % 4096) + 1 if (i * 73) % 4096 < 2047 else 0
                  for i in range(4096)]
    elif name == 'recursive_list':
        period = [n * (2045 - n) // 2 for n in range(512, 1024)]
    else:
        raise ValueError(name)
    cycles, rest = divmod(count, len(period))
    return cycles * sum(period) + sum(period[:rest])


def measure(compilers: dict[str, Path], output: Path, samples: int = 7) -> dict:
    if samples < 7:
        raise ValueError('At least seven paired samples are required')
    compilers = {name: path.resolve(strict=True) for name, path in compilers.items()}
    identities = {name: toolchain_identity(path) for name, path in compilers.items()}
    report = {'status': 'incomplete', 'toolchains': identities, 'workloads': {},
              'comparisons': {}, 'limits': [
                  'C uses ordinary pointer nodes without reference counts. Both languages '
                  'allocate each node separately before timing; destruction follows timing.',
                  'Both algorithms are identical. Allocation layout and value-copy semantics differ.',
                  'The historical fixed compiler cannot build these workloads; they extend '
                  'coverage without replacing the existing performance gate.']}
    save_report(output, report)
    for name, count in COUNTS.items():
        result = benchmark_apps.measure(compilers, [name], samples, 'cc', count=count,
                                        clock='thread-cpu', mode='both')
        # Remove descriptions of unrelated standard-suite kernels.
        result['limits'] = [s for s in result['limits']
                            if not s.startswith(('C graph', 'String equality'))]
        workload = result['workloads'][name]
        for size, actual in workload['preflight_checksums'].items():
            if actual != checksum(name, int(size)):
                raise RuntimeError(f'{name} count={size}: independent checksum mismatch')
        expected = checksum(name, count)
        if workload['checksum'] != expected:
            raise RuntimeError(f'{name}: expected {expected}, got {workload["checksum"]}')
        result['independent_checksum'] = expected
        report['workloads'][name] = result
        times = {label: [row['kernel_ns'] for row in rows]
                 for label, rows in workload['samples'].items()}
        report['comparisons'][name] = {
            f'{label}/c': compare_samples(times['c'], times[label], limit=1.0)
            for label in times if label != 'c'}
        if 'baseline' in compilers and 'candidate' in compilers:
            for mode in ('default', 'release'):
                report['comparisons'][name][f'candidate/{mode}/baseline'] = compare_samples(
                    times[f'baseline-{mode}'], times[f'candidate-{mode}'])
        save_report(output, report)
    if identities != {name: toolchain_identity(path) for name, path in compilers.items()}:
        raise RuntimeError('Toolchain changed during measurement')
    report['status'] = 'complete'
    save_report(output, report)
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--samples', type=int, default=7)
    cli.add_argument('--cpu', type=int)
    args = cli.parse_args()
    if args.cpu is not None:
        os.sched_setaffinity(0, {args.cpu})
    compilers = {'candidate': args.compiler}
    if args.baseline:
        compilers = {'baseline': args.baseline, **compilers}
    measure(compilers, args.output, args.samples)
