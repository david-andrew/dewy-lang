#!/usr/bin/env python3
"""Waiting-lane kernels versus pthreads; shared-host times are descriptive."""
import argparse
import os
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--runs', type=int, default=5)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    cpus = sorted(os.sched_getaffinity(0))[:4]
    os.sched_setaffinity(0, cpus)
    baseline = args.work / 'tasks-c'
    subprocess.run(['cc', '-O2', '-pthread', ROOT/'bench/tasks/tasks.c', '-o', baseline], check=True)
    for kernel, count in [('find_first', 1000000), ('race', 100), ('fanout', 10000)]:
        binary = args.work / kernel
        subprocess.run([args.compiler, 'build', ROOT/f'bench/tasks/{kernel}.dewy', '--release', '-o', binary], check=True)
        rows = [[], []]
        for repeat in range(args.runs):
            commands = [[binary, str(count)], [baseline, kernel, str(count)]]
            for index in ((0, 1) if repeat % 2 else (1, 0)):
                result = subprocess.run(commands[index], cwd=args.work, capture_output=True, text=True, check=True, timeout=30,
                                        env=dict(os.environ, SLOPPY_THREADS='4'))
                checksum, ns, latency = map(int, result.stdout.split())
                assert checksum == (count//4 if kernel == 'find_first' else count), result.stdout
                rows[index].append((ns, latency))
        times = [statistics.median(row[0] for row in samples) for samples in rows]
        latencies = [statistics.median(row[1] for row in samples) for samples in rows]
        print(f'{kernel} n={count} Dewy/C={times[0]/times[1]:.3f} ns={times} cancellation_ns={latencies} cpus={cpus} load={os.getloadavg()}', flush=True)


if __name__ == '__main__':
    main()
