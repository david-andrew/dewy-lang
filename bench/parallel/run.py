#!/usr/bin/env python3
"""Pinned, interleaved fork-join kernels against GCC/OpenMP.

Use --previous with a pre-change compiler to reproduce the upper-bound probe.
Artifacts live outside the checkout. Timing output is evidence, not a gate on
shared machines; --instructions also reports load-independent process counts.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import statistics
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SIZES = {'fib': 32, 'sum': 16777216, 'matmul': 1024,
         'jacobi': 1024, 'mergesort': 262144}
SMALL = {'fib': 16, 'sum': 10003, 'matmul': 65, 'jacobi': 31, 'mergesort': 1031}


def physical_cpus() -> list[int]:
    found = {}
    for cpu in sorted(os.sched_getaffinity(0)):
        topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        key = ((topology / 'physical_package_id').read_text().strip(),
               (topology / 'core_id').read_text().strip())
        found.setdefault(key, cpu)
    return list(found.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--workers', nargs='+', type=int, default=[1, 2, 4])
    parser.add_argument('--kernels', nargs='+', choices=SIZES, default=list(SIZES))
    parser.add_argument('--small', action='store_true', help='checksum smoke sizes')
    parser.add_argument('--instructions', action='store_true')
    parser.add_argument('--gate', action='store_true',
                        help='fail below 0.9x OpenMP or above 1.1x sequential time')
    parser.add_argument('--work', type=Path,
                        default=Path.home() / 'dev/tmp/astra-forkjoin/bench')
    args = parser.parse_args()
    if args.runs < 1 or any(n < 1 or n > 4 for n in args.workers):
        parser.error('positive run counts and 1–4 workers required')
    if args.gate and 1 not in args.workers:
        parser.error('--gate requires one-worker measurements')
    failed = False
    cpus = physical_cpus()
    if max(args.workers) > len(cpus):
        parser.error('not enough available physical cores')
    args.work.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('DEWY_', 'SLOPPY_', 'OMP_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    compilers = {'dewy': args.compiler.resolve()}
    if args.previous:
        compilers['previous'] = args.previous.resolve()
    counter = None
    if args.instructions:
        sys.path.insert(0, str(ROOT))
        from tools.compiler.speed import Counter, CACHE
        CACHE.mkdir(parents=True, exist_ok=True)
        counter = Counter('auto')
    print(f'load start: {os.getloadavg()}; physical CPUs: {cpus}', flush=True)
    sizes = SMALL if args.small else SIZES
    for kernel in args.kernels:
        source = ROOT / 'bench/parallel' / kernel
        binaries = {}
        for label, compiler in compilers.items():
            output = args.work / f'{kernel}-{label}'
            subprocess.run([compiler, 'build', source.with_suffix('.dewy'), '--release',
                            '-o', output], env=env, check=True)
            binaries[label] = output
        output = args.work / f'{kernel}-openmp'
        subprocess.run(['gcc', '-O3', '-fopenmp', source.with_suffix('.c'), '-o', output],
                       check=True)
        binaries['openmp'] = output
        expected = None
        measurements = {}
        for workers, serial in [(n, False) for n in args.workers] + [(1, True)]:
            samples = {label: [] for label in binaries}
            counts = {label: [] for label in binaries}
            run_env = dict(env, SLOPPY_THREADS=str(workers), OMP_NUM_THREADS=str(workers),
                           OMP_PROC_BIND='true', OMP_PLACES='cores')
            for repeat in range(args.runs):
                order = list(binaries)
                if repeat % 2:
                    order.reverse()
                for label in order:
                    command = [shutil.which('taskset'), '-c', ','.join(map(str, cpus[:workers])),
                               str(binaries[label]), str(sizes[kernel])]
                    if serial:
                        command.append('serial')
                    result = subprocess.run(command, env=run_env, capture_output=True,
                                            text=True, check=True, timeout=120)
                    checksum, ns = map(int, result.stdout.split())
                    if expected is None:
                        expected = checksum
                    if checksum != expected:
                        raise RuntimeError(f'{kernel}/{label}: {checksum} != {expected}')
                    samples[label].append(ns / 1e6)
                    if counter:
                        instructions, output = counter.run(command, run_env)
                        if int(output.split()[0]) != expected:
                            raise RuntimeError(f'{kernel}/{label}: counter checksum mismatch')
                        counts[label].append(instructions)
            label = 'serial' if serial else str(workers)
            exact = {k: statistics.median(v) for k, v in samples.items()}
            measurements[label] = exact
            medians = {k: round(v, 3) for k, v in exact.items()}
            print(f'{kernel:10} {label:6} ms={medians} checksum={expected} '
                  f'load={os.getloadavg()}', flush=True)
            if counter:
                print('  instructions (whole process, including setup): '
                      + str({k: int(statistics.median(v)) for k, v in counts.items()}),
                      flush=True)
        if args.gate:
            for workers in args.workers:
                times = measurements[str(workers)]
                ratio = times['openmp'] / times['dewy']
                if ratio < 0.9:
                    print(f'FAIL {kernel}/{workers}: {ratio:.3f}x OpenMP < 0.9x', flush=True)
                    failed = True
            overhead = measurements['1']['dewy'] / measurements['serial']['dewy']
            if overhead > 1.1:
                print(f'FAIL {kernel}: T1/Tseq={overhead:.3f} > 1.1', flush=True)
                failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
