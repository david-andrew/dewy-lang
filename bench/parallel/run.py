#!/usr/bin/env python3
"""Pinned, interleaved fork-join kernels against GCC/OpenMP.

Use --previous with a pre-change compiler to reproduce the upper-bound probe.
Artifacts go under build/ (untracked). Timing output is evidence, not a gate on
shared machines; --instructions also reports load-independent process counts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SIZES = {'fib': 32, 'sum': 16777216, 'matmul': 1024,
         'jacobi': 1024, 'mergesort': 262144, 'parallel_particles': 2048}
SMALL = {'fib': 16, 'sum': 10003, 'matmul': 65, 'jacobi': 31, 'mergesort': 1031, 'parallel_particles': 65}


def gate_failures(measurements: dict, workers: list[int], *, instructions=False) -> list[str]:
    """Keep timing and instruction gates separate: counters cannot establish scaling."""
    failures = []
    t1 = measurements['1']['dewy']
    if not instructions:
        for n in workers:
            times = measurements[str(n)]
            ratio = times['openmp'] / times['dewy']
            if ratio < 0.9:
                failures.append(f'{n} workers: {ratio:.3f}x OpenMP < 0.9x')
            speedup = t1 / times['dewy']
            c_speedup = measurements['1']['openmp'] / times['openmp']
            if n > 1 and speedup < 0.9 * c_speedup:
                failures.append(f'{n} workers: scaling {speedup:.3f}x < 0.9 * OpenMP {c_speedup:.3f}x')
    overhead = t1 / measurements['serial']['dewy']
    if overhead > 1.1:
        metric = 'instructions' if instructions else 'time'
        failures.append(f'T1/Tseq {metric}={overhead:.3f} > 1.1')
    return failures


def physical_cpus() -> list[int]:
    found = {}
    for cpu in sorted(os.sched_getaffinity(0)):
        topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        key = ((topology / 'physical_package_id').read_text().strip(),
               (topology / 'core_id').read_text().strip())
        found.setdefault(key, cpu)
    return list(found.values())


def selected_cpus(allow_smt=False) -> list[int]:
    cores = physical_cpus()
    return cores + sorted(set(os.sched_getaffinity(0)) - set(cores)) if allow_smt else cores


def count_pinned(counter, command: list, env: dict, cpus: list[int]):
    # Pin the parent temporarily, so the counter and exec'd kernel inherit the
    # mask. Valgrind does not follow taskset's exec without --trace-children;
    # counting the executable directly also removes wrapper startup noise.
    previous = os.sched_getaffinity(0)
    try:
        os.sched_setaffinity(0, cpus)
        return counter.run(command, env)
    finally:
        os.sched_setaffinity(0, previous)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--workers', nargs='+', type=int, default=[1, 2, 4])
    parser.add_argument('--kernels', nargs='+', choices=SIZES, default=list(SIZES))
    parser.add_argument('--small', action='store_true', help='checksum smoke sizes')
    parser.add_argument('--allow-smt', action='store_true',
                        help='use SMT siblings after distinct cores; report worker counts, not physical-core scaling')
    parser.add_argument('--instructions', action='store_true')
    parser.add_argument('--instruction-gate', action='store_true',
                        help='count instructions and fail above 1.1x sequential instructions')
    parser.add_argument('--report', type=Path, help='write samples, medians and gate failures as JSON')
    parser.add_argument('--cycles', action='store_true', help='indicative pinned hardware cycles')
    parser.add_argument('--gate', action='store_true',
                        help='fail below 0.9x OpenMP throughput/scaling or above 1.1x sequential time')
    parser.add_argument('--work', type=Path,
                        default=ROOT / 'build/forkjoin-bench')
    args = parser.parse_args()
    if args.runs < 1 or any(n < 1 or n > 4 for n in args.workers):
        parser.error('positive run counts and 1–4 workers required')
    if (args.gate or args.instruction_gate) and 1 not in args.workers:
        parser.error('gates require one-worker measurements')
    args.instructions |= args.instruction_gate
    failed = False
    cpus = selected_cpus(args.allow_smt)
    if max(args.workers) > len(cpus):
        parser.error('not enough CPUs (use --allow-smt explicitly to include SMT siblings)')
    args.work.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('DEWY_', 'OMP_'))}
    env['DEWY_EMIT_WORKERS'] = '1'
    compilers = {'dewy': args.compiler.resolve()}
    if args.previous:
        compilers['previous'] = args.previous.resolve()
    counter = None
    if args.instructions or args.cycles:
        sys.path.insert(0, str(ROOT))
        from tools.compiler.speed import Counter, CACHE
        CACHE.mkdir(parents=True, exist_ok=True)
        counter = Counter('perf' if args.cycles else 'auto')
    print(f'load start: {os.getloadavg()}; physical CPUs: {physical_cpus()}; selected CPUs: {cpus}', flush=True)
    report = {'physical_cpus': physical_cpus(), 'selected_cpus': cpus, 'load_start': os.getloadavg(),
              'uses_smt': max(args.workers) > len(physical_cpus()),
              'workers': args.workers, 'runs': args.runs, 'kernels': {},
              'counter': counter.label if counter else None,
              'wall_gate': args.gate, 'instruction_gate': args.instruction_gate}
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
        subprocess.run(['gcc', '-O3', '-fopenmp', source.with_suffix('.c'), '-lm', '-o', output],
                       check=True)
        binaries['openmp'] = output
        expected = None
        measurements = {}
        instruction_measurements = {}
        rows = {}
        for workers, serial in [(n, False) for n in args.workers] + [(1, True)]:
            samples = {label: [] for label in binaries}
            counts = {label: [] for label in binaries}
            cycles = {label: [] for label in binaries}
            run_env = dict(env, DEWY_THREADS=str(workers), OMP_NUM_THREADS=str(workers),
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
                    if args.instructions:
                        instructions, output = count_pinned(counter, command[3:], run_env, cpus[:workers])
                        if int(output.split()[0]) != expected:
                            raise RuntimeError(f'{kernel}/{label}: counter checksum mismatch')
                        counts[label].append(instructions)
                    if args.cycles:
                        from tools.compiler.speed import counter_result
                        measured = subprocess.run([counter.binary, '--cycles', *command],
                                                  env=run_env, capture_output=True,
                                                  text=True, check=True, timeout=120)
                        if int(measured.stdout.split()[0]) != expected:
                            raise RuntimeError(f'{kernel}/{label}: cycle checksum mismatch')
                        cycles[label].append(counter_result(measured.stderr, 'cycles'))
            label = 'serial' if serial else str(workers)
            exact = {k: statistics.median(v) for k, v in samples.items()}
            measurements[label] = exact
            rows[label] = {'ms': samples, 'instructions': counts, 'cycles': cycles}
            medians = {k: round(v, 3) for k, v in exact.items()}
            print(f'{kernel:10} {label:6} ms={medians} checksum={expected} '
                  f'load={os.getloadavg()}', flush=True)
            if args.instructions:
                instruction_measurements[label] = {k: statistics.median(v) for k, v in counts.items()}
                print('  instructions (whole process, including setup): '
                      + str({k: int(statistics.median(v)) for k, v in counts.items()}),
                      flush=True)
            if args.cycles:
                print('  cycles (whole process, indicative on a shared host): '
                      + str({k: int(statistics.median(v)) for k, v in cycles.items()}), flush=True)
            print('  range ms: ' + str({k: (round(min(v), 3), round(max(v), 3))
                                        for k, v in samples.items()}), flush=True)
        for implementation in binaries:
            t1 = measurements['1'][implementation] if '1' in measurements else None
            if t1 is not None:
                print(f'  {implementation} T1/Tseq={t1 / measurements["serial"][implementation]:.3f}; '
                      + 'speedups ' + str({n: round(t1 / measurements[str(n)][implementation], 3)
                                          for n in args.workers}), flush=True)
                if args.instructions:
                    ratio = instruction_measurements['1'][implementation] / instruction_measurements['serial'][implementation]
                    print(f'  {implementation} instruction T1/Tseq={ratio:.6f}', flush=True)
        print('  OpenMP/Dewy rates: ' + str({n: round(measurements[str(n)]['openmp'] /
              measurements[str(n)]['dewy'], 3) for n in args.workers}), flush=True)
        failures = gate_failures(measurements, args.workers) if args.gate else []
        if args.instruction_gate:
            failures += gate_failures(instruction_measurements, args.workers, instructions=True)
        for failure in failures:
            print(f'FAIL {kernel}: {failure}', flush=True)
        failed |= bool(failures)
        report['kernels'][kernel] = {'size': sizes[kernel], 'checksum': expected, 'samples': rows,
                                     'median_ms': measurements, 'median_instructions': instruction_measurements,
                                     'failures': failures}
        # Publish after each kernel, so a later build/run failure retains completed rows.
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + '\n')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
