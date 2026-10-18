"""Measure fused array expressions and comprehensions against the same C kernel."""
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

from tools.sloppy_core.benchmark_apps import ROOT, digest, prepare_clock, run
from tools.sloppy_core.benchmark_compile import positive

DEWY = '''from p"benchmark_harness.jo" import clock
kernel=(a:array<float64> b:array<float64> phase:float64):>array<float64>=>EXPRESSION
main=(args:array<string>)=>{
    let n=to_int(args[1]) ?? 262144
    let steps=to_int(args[2]) ?? 64
    let a=[loop i in [0..n) (((i*7)%17-8) as float64)/8.0]
    let b=[loop i in [0..n) (((i*11)%19-9) as float64)/8.0]
    let result=kernel(a b 0.0)
    assert(result.length =? n)
    if n >? 0 {assert(result[0] =? -2.5625)}
    let start=clock()
    loop iteration in [0..steps) {
        result=kernel(a b ((iteration%8) as float64)/8.0)
    }
    let elapsed=clock()-start
    let checksum=0
    loop i in [0..result.length) {checksum+=((result[i]*16.0) as int64)*(i%31+1)}
    printl"{checksum} {elapsed}"
    return 0
}
'''
EXPRESSIONS = {
    'fused': 'a .* 2.0 .+ b .* 0.5 .+ phase',
    'loop': '[loop i in [0..a.length) a[i]*2.0+b[i]*0.5+phase]',
    'values': '[loop i in 0.. and x in a x*2.0+b[i]*0.5+phase]',
}
C = '''#define _POSIX_C_SOURCE 200809L
#include "harness.h"
static double *kernel(const double *a, const double *b, int n, double phase) {
    double *out=malloc(((size_t)n+1)*sizeof(double));
    if (!out) exit(2);
    for (int i=0; i<n; ++i) out[i]=a[i]*2.0+b[i]*0.5+phase;
    return out;
}
int main(int argc, char **argv) {
    if (argc!=3) return 2;
    int n=atoi(argv[1]), steps=atoi(argv[2]);
    if (n<0 || n>16777216 || steps<1) return 2;
    double *a=malloc(((size_t)n+1)*sizeof(double));
    double *b=malloc(((size_t)n+1)*sizeof(double));
    if (!a || !b) return 2;
    for (int i=0; i<n; ++i) {
        a[i]=((i*7)%17-8)/8.0;
        b[i]=((i*11)%19-9)/8.0;
    }
    double *result=kernel(a,b,n,0.0);
    if (n>0 && result[0]!=-2.5625) return 2;
    int64_t start=clock_now();
    for (int iteration=0; iteration<steps; ++iteration) {
        double *next=kernel(a,b,n,(iteration%8)/8.0);
        free(result); result=next;
    }
    int64_t elapsed=clock_now()-start, checksum=0;
    for (int i=0; i<n; ++i) checksum+=(int64_t)(result[i]*16.0)*(i%31+1);
    report(checksum,elapsed);
    free(result); free(a); free(b);
    return 0;
}
'''


def expected_checksum(count: int, steps: int) -> int:
    phase = (steps - 1) % 8
    return sum((4 * ((i * 7) % 17 - 8) + (i * 11) % 19 - 9 + 2 * phase) * (i % 31 + 1)
               for i in range(count))


def measure(compiler: Path, baseline: Path | None, count: int, steps: int,
            samples: int, cc: str, clock: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_EMIT_WORKERS='1', SLOPPY_THREADS='1')
    compilers = {'baseline': baseline, 'candidate': compiler} if baseline else {'core': compiler}
    report = {
        'compilers': {label: {'path': str(path), 'sha256': digest(path)} for label, path in compilers.items()},
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'platform': platform.platform(), 'cpu_affinity': sorted(os.sched_getaffinity(0)),
        'count': count, 'steps': steps, 'samples': samples, 'kernel_clock': clock,
        'load_average_start': os.getloadavg(),
        'limits': ['Native float64; one thread; no GPU.',
                   'Input initialization and one warmup kernel are outside timing.',
                   'Allocation of each result and release of the preceding result are included.',
                   'The phase changes on every iteration; inputs and operations match C.',
                   'Dyadic inputs allow an exact independent integer checksum, including full-size runs.',
                   'Alternating sample order; CPU frequency and cache contention can still vary.'],
    }
    with tempfile.TemporaryDirectory(prefix='dewy-broadcast-') as directory:
        work = Path(directory)
        shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', work)
        report['harness_sha256'] = prepare_clock(work, clock)
        binaries, builds, sources = {}, {}, {}
        for form, expression in EXPRESSIONS.items():
            source = work / f'{form}.dewy'
            source.write_text(DEWY.replace('EXPRESSION', expression))
            sources[form] = digest(source)
            for label, path in compilers.items():
                for mode in ['default', 'release']:
                    name = f'{label}-{form}-{mode}'
                    binary = work / name
                    _, builds[name] = run([path, 'build', source, '-o', binary,
                                          *(['--release'] if mode == 'release' else [])], env)
                    binaries[name] = binary
        source = work / 'reference.c'
        source.write_text(C)
        sources['c'] = digest(source)
        c_flags = ['-O3', '-march=native', '-ffp-contract=off', '-std=c11']
        binaries['c'] = work / 'reference'
        _, builds['c'] = run([cc, *c_flags, source, '-o', binaries['c']], env)
        report.update(source_sha256=sources, build_seconds=builds, c_flags=c_flags,
                      c_version=run([cc, '--version'], env)[0].splitlines()[0],
                      binary_sha256={label: digest(path) for label, path in binaries.items()})

        def execute(label, size, iterations):
            output, _ = run([binaries[label], str(size), str(iterations)], env)
            checksum, ns = map(int, output.split())
            if ns < 0:
                raise RuntimeError(f'{label}: negative kernel time')
            return checksum, ns

        preflight = {}
        for size in [0, 1, 17, 65]:
            expected = expected_checksum(size, 3)
            for label in binaries:
                checksum, _ = execute(label, size, 3)
                if checksum != expected:
                    raise RuntimeError(f'{label}, n={size}: checksum {checksum}, expected {expected}')
            preflight[str(size)] = expected
        expected = expected_checksum(count, steps)
        measured = {label: [] for label in binaries}
        labels = list(binaries)
        for sample in range(samples + 1):
            for label in (labels if sample % 2 == 0 else labels[::-1]):
                checksum, ns = execute(label, count, steps)
                if checksum != expected:
                    raise RuntimeError(f'{label}: checksum {checksum}, expected {expected}')
                if sample:
                    measured[label].append(ns)
        report.update(preflight_checksums=preflight, checksum=expected, nanoseconds=measured,
                      median_ms={label: statistics.median(ns) / 1e6 for label, ns in measured.items()},
                      paired_over_c={label: statistics.median(a / b for a, b in zip(ns, measured['c'], strict=True))
                                     for label, ns in measured.items() if label != 'c'})
        if baseline:
            report['paired_candidate_over_baseline'] = {
                f'{form}-{mode}': statistics.median(a / b for a, b in zip(
                    measured[f'candidate-{form}-{mode}'], measured[f'baseline-{form}-{mode}'], strict=True))
                for form in EXPRESSIONS for mode in ['default', 'release']}
    report['load_average_end'] = os.getloadavg()
    print(report['median_ms'], flush=True)
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--count', type=positive, default=262144)
    cli.add_argument('--steps', type=positive, default=64)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--cc', default='cc')
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='thread-cpu')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    if args.count > 16777216:
        cli.error('--count must be at most 16777216')
    result = measure(args.compiler.resolve(strict=True), args.baseline.resolve(strict=True) if args.baseline else None,
                     args.count, args.steps, args.samples, args.cc, args.clock)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
