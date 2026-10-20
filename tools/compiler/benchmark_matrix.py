"""Compare bundled matrix multiplication with the same flat-buffer C algorithm."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from tools.compiler.benchmark_compile import positive

ROOT = Path(__file__).resolve().parents[2]
DEWY = '''main=(args:array<string>)=>{
    let n=to_int(args[1]) ?? 192
    let steps=to_int(args[2]) ?? 8
    let a=reshape([loop i in [0..n*n) ((((i//n)*7+(i%n)*3)%17-8) as float64)/8.0] n n)
    let b=reshape([loop i in [0..n*n) ((((i//n)*5+(i%n)*11)%19-9) as float64)/8.0] n n)
    let result=a*b
    let start=time_ns()
    loop iteration in [0..steps) {result=a*b}
    let elapsed=time_ns()-start
    let checksum=0
    loop i in [0..result.data.length) {checksum+=((result.data[i]*64.0) as int64)*(i+1)}
    printl("{checksum} {elapsed}")
    return 0
}
'''
C = r'''#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static int64_t now(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) exit(2);
    return (int64_t)ts.tv_sec*1000000000 + ts.tv_nsec;
}
static double *product(const double *a, const double *b, int n) {
    double *out = calloc((size_t)n*n + 1, sizeof(double));
    if (!out) exit(2);
    for (int i=0; i<n; ++i) {
        for (int k=0; k<n; ++k) {
            double x=a[i*n+k];
            if (x==0.0) continue;
            for (int j=0; j<n; ++j) out[i*n+j] += x*b[k*n+j];
        }
    }
    return out;
}
int main(int argc, char **argv) {
    if (argc!=3) return 2;
    int n=atoi(argv[1]), steps=atoi(argv[2]);
    if (n<0 || n>2048 || steps<1) return 2;
    double *a=malloc(((size_t)n*n+1)*sizeof(double));
    double *b=malloc(((size_t)n*n+1)*sizeof(double));
    if (!a || !b) return 2;
    for (int i=0; i<n; ++i) for (int j=0; j<n; ++j) {
        a[i*n+j]=((i*7+j*3)%17-8)/8.0;
        b[i*n+j]=((i*5+j*11)%19-9)/8.0;
    }
    double *result=product(a,b,n);
    int64_t start=now();
    for (int iteration=0; iteration<steps; ++iteration) {
        double *next=product(a,b,n);
        free(result);
        result=next;
    }
    int64_t elapsed=now()-start, checksum=0;
    for (int i=0; i<n*n; ++i) checksum+=(int64_t)(result[i]*64.0)*(i+1);
    printf("%lld %lld\n", (long long)checksum, (long long)elapsed);
    free(result); free(a); free(b);
    return 0;
}
'''


def expected_checksum(n: int) -> int:
    """Integer reference: each product has denominator 64, with no rounding."""
    a = [[(i * 7 + k * 3) % 17 - 8 for k in range(n)] for i in range(n)]
    b = [[(k * 5 + j * 11) % 19 - 9 for j in range(n)] for k in range(n)]
    return sum(sum(a[i][k] * b[k][j] for k in range(n)) * (i * n + j + 1)
               for i in range(n) for j in range(n))


def measure(compiler: Path, size: int, steps: int, samples: int, threads: int, cc: str,
            baseline: Path | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    compilers = {'baseline': baseline, 'candidate': compiler} if baseline else {'core': compiler}
    report = {
        'compilers': {label: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                      for label, path in compilers.items()},
        'platform': platform.platform(), 'cpu_affinity': sorted(os.sched_getaffinity(0)),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'size': size, 'steps': steps, 'samples': samples, 'threads_requested': threads,
        'load_average_start': os.getloadavg(),
        'source_sha256': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in [('dewy', DEWY), ('c', C)]},
        'limits': ['Native float64 square matrices, identical row/k/column loop order and zero skipping.',
                   'The timed region includes allocation/zeroing and releasing the previous result.',
                   'Initialization and one multiplication (including worker startup) precede timing.',
                   'Wall-clock kernel time; C always uses one thread. Compare single-thread variants for language cost.',
                   'Dyadic input values make every multiply/add exact at these sizes; checksums do not need tolerances.',
                   'This is the bundled matrix operator, not a claim about arbitrary user-written loops or a tuned BLAS.'],
    }

    def run(command, child_env=env):
        result = subprocess.run(command, env=child_env, capture_output=True, text=True,
                                timeout=120, check=False)
        if result.returncode:
            raise RuntimeError(f'{command}:\n{result.stdout}{result.stderr}')
        return result.stdout

    with tempfile.TemporaryDirectory(prefix='dewy-matrix-') as directory:
        work = Path(directory)
        source = work / 'matrix.dewy'
        source.write_text(DEWY)
        c_source = work / 'matrix.c'
        c_source.write_text(C)
        builds, binaries = {}, {}
        for label, path in compilers.items():
            for mode in ['default', 'release']:
                name = f'{label}-{mode}'
                binary = work / name
                start = time.perf_counter()
                run([path, 'build', source, '-o', binary, *(['--release'] if mode == 'release' else [])])
                builds[name] = time.perf_counter() - start
                binaries[name] = binary
        c_binary = work / 'reference'
        c_flags = ['-O3', '-march=native', '-ffp-contract=off', '-std=c11']
        run([cc, *c_flags, c_source, '-o', c_binary])
        report.update(build_seconds=builds, c_flags=c_flags, c_version=run([cc, '--version']).splitlines()[0],
                      binary_sha256={k: hashlib.sha256(v.read_bytes()).hexdigest()
                                     for k, v in {**binaries, 'c': c_binary}.items()})
        counts = sorted({1, threads})
        variants = {f'{mode}-{count}': (binary, count)
                    for mode, binary in binaries.items() for count in counts}
        variants['c'] = (c_binary, 1)

        def execute(label, n, iterations):
            binary, count = variants[label]
            output = run([binary, str(n), str(iterations)], {**env, 'SLOPPY_THREADS': str(count)})
            checksum, ns = map(int, output.split())
            if ns < 0:
                raise RuntimeError(f'{label}: negative elapsed time')
            return checksum, ns

        preflight = {}
        for n in [0, 1, 17, 65]:
            expected = expected_checksum(n)
            for label in variants:
                checksum, _ = execute(label, n, 2)
                if checksum != expected:
                    raise RuntimeError(f'{label}, n={n}: checksum {checksum}, expected {expected}')
            preflight[str(n)] = expected
        expected, _ = execute('c', size, 1)
        measured = {label: [] for label in variants}
        labels = list(variants)
        for sample in range(samples + 1):
            for label in (labels if sample % 2 == 0 else labels[::-1]):
                checksum, ns = execute(label, size, steps)
                if checksum != expected:
                    raise RuntimeError(f'{label}: checksum {checksum}, expected {expected}')
                if sample:
                    measured[label].append(ns)
        report.update(preflight_checksums=preflight, checksum=expected, nanoseconds=measured,
                      median_ms={k: statistics.median(v) / 1e6 for k, v in measured.items()},
                      paired_over_c={label: statistics.median(a / b for a, b in zip(values, measured['c']))
                                     for label, values in measured.items() if label != 'c'})
        if threads != 1:
            report['paired_parallel_over_serial'] = {
                mode: statistics.median(a / b for a, b in zip(measured[f'{mode}-{threads}'], measured[f'{mode}-1']))
                for mode in binaries}
        if baseline:
            report['paired_candidate_over_baseline'] = {
                f'{mode}-{count}': statistics.median(a / b for a, b in zip(
                    measured[f'candidate-{mode}-{count}'], measured[f'baseline-{mode}-{count}']))
                for mode in ['default', 'release'] for count in counts}
    report['load_average_end'] = os.getloadavg()
    print(report['median_ms'], flush=True)
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--size', type=positive, default=192)
    cli.add_argument('--steps', type=positive, default=8)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--threads', type=positive, default=2)
    cli.add_argument('--cc', default='cc')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    if args.size > 2048:
        cli.error('--size must be at most 2048')
    result = measure(args.compiler.resolve(strict=True), args.size, args.steps, args.samples, args.threads,
                     args.cc, args.baseline.resolve(strict=True) if args.baseline else None)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
