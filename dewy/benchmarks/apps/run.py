#!/usr/bin/env python3
"""Build and time the application benchmarks.

    run.py COMPILER_DIR [--rounds N] [--only NAME ...]

COMPILER_DIR holds the native `dewy` compiler and its `udewy`. Every workload
is built three ways -- the default route, the optimizing route (opt-in as
DEWY_EMIT=native while it grows) and its C counterpart with `cc -O2` -- and
run at a small and a larger input. A program times its own kernel, so setup
is not counted; the best and the median of N rounds are reported, with the
whole run, compile latency and peak memory beside them. The checksums of the three builds must agree.
"""
import argparse, os, platform, resource, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORKLOADS = {  # name: (small input, larger input)
    'helpers': (200_000, 2_000_000),
    'arrays': (1_000_000, 10_000_000),
    'records': (100_000, 1_000_000),
    'text': (1_000_000, 10_000_000),
    'graph': (200_000, 1_000_000),
}
CC = ['cc', '-O2']


def measured(command, env=None, cwd=None):
    """Run `command`: (stdout, wall seconds, peak KiB of the child)."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    started = time.perf_counter()
    done = subprocess.run(command, env=env, cwd=cwd, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    if done.returncode != 0:
        sys.exit(f'failed: {" ".join(map(str, command))}\n{done.stdout}{done.stderr}')
    # ru_maxrss is the largest child so far: a smaller later one reads as the earlier peak.
    return done.stdout, elapsed, max(before, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)


def peak(command):
    done = subprocess.run(['/usr/bin/time', '-f', '%M', *command], capture_output=True, text=True)
    return int(done.stderr.strip().splitlines()[-1])


def build_dewy(compiler, name, route, out):
    env = dict(os.environ, DEWY_UDEWY=str(compiler / 'udewy'), DEWY_LIBRARY_ROOT=str(ROOT / 'library'))
    env.pop('DEWY_EMIT', None)
    if route == 'optimizing':
        env['DEWY_EMIT'] = 'native'
    cache = ROOT / '__dewycache__' / HERE.relative_to(ROOT)
    for stale in cache.glob(f'{name}*'):
        stale.unlink()
    command = [str(compiler / 'dewy'), '-c', str(HERE / f'{name}.dewy')]
    _, seconds, _ = measured(command, env=env, cwd=ROOT)
    memory = peak(['env', *(f'{k}={v}' for k, v in env.items() if k.startswith('DEWY_')), *command])
    shutil.copy(cache / name, out)
    return seconds, memory


def build_c(name, out):
    command = [*CC, '-o', str(out), str(HERE / f'{name}.c')]
    _, seconds, _ = measured(command)
    return seconds, peak(command)


def kernel(binary, size, rounds):
    """Run `rounds` times: (checksum, kernel ms best and median, whole-run ms best, peak KiB)."""
    kernels, runs, checksum = [], [], None
    for _ in range(rounds):
        started = time.perf_counter()
        fields = subprocess.run([str(binary), str(size)], capture_output=True, text=True, check=True).stdout.split()
        runs.append((time.perf_counter() - started) * 1e3)
        if checksum not in (None, fields[0]):
            sys.exit(f'{binary}: checksum changed between rounds')
        checksum = fields[0]
        kernels.append(int(fields[1]) / 1e6)
    return checksum, min(kernels), statistics.median(kernels), min(runs), peak([str(binary), str(size)])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('compiler', type=Path)
    parser.add_argument('--rounds', type=int, default=5)
    parser.add_argument('--only', nargs='*', default=list(WORKLOADS))
    options = parser.parse_args()
    compiler = options.compiler.resolve()
    cc = subprocess.run([CC[0], '--version'], capture_output=True, text=True).stdout.splitlines()[0]
    cpu = next((line.split(':', 1)[1].strip() for line in open('/proc/cpuinfo') if line.startswith('model name')), platform.machine())
    print(f'machine: {cpu}; {platform.system()} {platform.release()}')
    print(f'C: `{" ".join(CC)}` ({cc}); rounds: best of {options.rounds}\n')
    print('| workload | build | compile s | compile MiB | input | kernel ms | median | vs C | whole run ms | run MiB |')
    print('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    with tempfile.TemporaryDirectory(dir=os.environ.get('DEWY_BENCH_TMP')) as scratch:
        for name in options.only:
            builds = {}
            for route in ('default', 'optimizing'):
                out = Path(scratch) / f'{name}-{route}'
                builds[route] = (out, *build_dewy(compiler, name, route, out))
            out = Path(scratch) / f'{name}-c'
            builds['C'] = (out, *build_c(name, out))
            for size in WORKLOADS[name]:
                results = {route: kernel(binary, size, options.rounds) for route, (binary, _, _) in builds.items()}
                if len({result[0] for result in results.values()}) != 1:
                    sys.exit(f'{name} {size}: checksums differ: {results}')
                for route, (_, seconds, memory) in builds.items():
                    _, best, median, whole, run_memory = results[route]
                    print(f'| {name} | {route} | {seconds:.2f} | {memory / 1024:.0f} | {size} | {best:.1f} | {median:.1f} | {best / results["C"][1]:.2f}x | {whole:.1f} | {run_memory / 1024:.1f} |', flush=True)


if __name__ == '__main__':
    main()
