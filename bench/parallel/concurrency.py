#!/usr/bin/env python3
"""Counters and histogram against C/OpenMP, capped at four workers.

Wall times on a shared host are descriptive, never a landing gate. Scratch
and timing output stay outside the checkout.
"""
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
    parser.add_argument('--count', type=int, default=1000000)
    parser.add_argument('--runs', type=int, default=5)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    for kernel in ('counters', 'histogram'):
        source = ROOT / 'bench/parallel' / kernel
        binaries = [args.work / (kernel + suffix) for suffix in ('-dewy', '-c')]
        subprocess.run([args.compiler, 'build', source.with_suffix('.dewy'), '--release', '-o', binaries[0]], check=True)
        subprocess.run(['cc', '-O2', '-fopenmp', source.with_suffix('.c'), '-o', binaries[1]], check=True)
        for workers in (1, 2, 4):
            for padded in ([False, True] if kernel == 'counters' else [False]):
                times = [[], []]
                checksum = None
                for repeat in range(args.runs):
                    for index in ((0, 1) if repeat % 2 else (1, 0)):
                        result = subprocess.run([binaries[index], str(args.count), *(['padded'] if padded else [])],
                                                env=dict(os.environ, SLOPPY_THREADS=str(workers), OMP_NUM_THREADS=str(workers)),
                                                capture_output=True, text=True, check=True, timeout=60)
                        value, ns = map(int, result.stdout.split())
                        assert checksum is None or value == checksum, result.stdout
                        checksum = value
                        times[index].append(ns)
                medians = [statistics.median(t) for t in times]
                print(f'{kernel} workers={workers} padded={padded} checksum={checksum} '
                      f'Dewy/C={medians[0]/medians[1]:.3f} ns={medians} load={os.getloadavg()}', flush=True)


if __name__ == '__main__':
    main()
