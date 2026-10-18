"""Measure the five original Dewy application workloads against C and an optional core baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from tools.sloppy_core.benchmark_compile import positive

ROOT = Path(__file__).resolve().parents[2]
APPS = ROOT / 'dewy/benchmarks/apps'
COUNTS = {'helpers': 2000000, 'arrays': 10000000, 'records': 1000000,
          'text': 10000000, 'graph': 1000000}
CHECKSUMS_1000 = {'helpers': 985290002, 'arrays': 876830114, 'records': 649125068,
                  'text': 681360428, 'graph': 740553269}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_source(name: str, directory: Path) -> Path:
    """Adapt only the platform harness and the old pointer-sized index spelling."""
    source = directory / f'{name}.dewy'
    source.write_text((APPS / f'{name}.dewy').read_text()
                      .replace('p"harness.dewy"', 'p"benchmark_harness.jo"')
                      .replace(':addr', ':int64'))
    shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', directory)
    return source


def prepare_clock(directory: Path, clock: str) -> dict[str, str]:
    """Use the same kernel clock in Dewy and C, retaining the original sources."""
    harness = directory / 'benchmark_harness.jo'
    c_header = (APPS / 'harness.h').read_text()
    if clock == 'thread-cpu':
        if platform.system() != 'Linux':
            raise RuntimeError('Thread CPU timing currently requires Linux')
        timer = '''clock = () -> int:
    ts: (int, int)
    if syscall(228, 3, &ts) != 0: panic("thread CPU clock unavailable")
    ts.0 * 1000000000 + ts.1'''
        original = harness.read_text()
        if original.count('clock = () -> int: time_ns()') != 1 or c_header.count('CLOCK_MONOTONIC') != 1:
            raise RuntimeError('Benchmark clocks changed; update the thread CPU adaptation')
        harness.write_text(original.replace('clock = () -> int: time_ns()', timer))
        c_header = c_header.replace('CLOCK_MONOTONIC', 'CLOCK_THREAD_CPUTIME_ID')
    elif clock != 'wall':
        raise ValueError(f'Unknown kernel clock: {clock}')
    (directory / 'harness.h').write_text(c_header)
    return {'dewy': digest(harness), 'c': digest(directory / 'harness.h')}


def run(command: list, env: dict) -> tuple[str, float]:
    started = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                            text=True, timeout=120, check=False)
    elapsed = time.perf_counter() - started
    if result.returncode:
        raise RuntimeError(f'{command}:\n{result.stdout}{result.stderr}')
    return result.stdout, elapsed


def execute(binary: Path, count: int, env: dict) -> tuple[int, dict]:
    output, elapsed = run([binary, str(count)], env)
    checksum, ns = map(int, output.split())
    if ns < 0:
        raise RuntimeError(f'{binary}: negative kernel time')
    return checksum, {'kernel_ns': ns, 'wall_seconds': elapsed}


def measure(compilers: dict[str, Path], workloads: list[str], samples: int,
            cc: str, count: int | None = None, clock: str = 'wall', mode: str = 'release') -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    modes = ['default', 'release'] if mode == 'both' else [mode]
    variants = {label if mode != 'both' else f'{label}-{build_mode}':
                (label, [] if build_mode == 'default' else ['--release'])
                for label in compilers for build_mode in modes}
    result = {
        'platform': platform.platform(),
        'cpu_affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
        'load_average_start': os.getloadavg(),
        'samples': samples,
        'kernel_clock': clock,
        'warmups_per_binary': 1,
        'mode': mode,
        'core_flags': [] if mode == 'default' else ['--release'] if mode == 'release' else None,
        'variants': {label: {'compiler': compiler, 'flags': flags}
                     for label, (compiler, flags) in variants.items()},
        'emission_workers': 1,
        'cc': run([cc, '--version'], env)[0],
        'c_flags': ['-O2'],
        'compilers': {},
        'adaptations': ['Replace the platform harness import', 'Replace :addr with :int64'],
        'harness_sha256': digest(ROOT / 'tools/sloppy_core/benchmark_harness.jo'),
        'c_harness_sha256': digest(APPS / 'harness.h'),
        'workloads': {},
        'limits': ['Native 64-bit host; warm filesystem caches; one build per binary.',
                   'C graph uses flat edges and a handwritten map; Dewy uses per-node arrays and an insertion-ordered map.',
                   'Kernel times exclude input generation; wall times include the complete process.',
                   'Thread CPU timing excludes descheduling, but CPU frequency and cache contention still matter.'],
    }
    for label, compiler in compilers.items():
        identity = {'path': str(compiler), 'sha256': digest(compiler)}
        manifest = compiler.parent.parent / 'build.json'
        if manifest.exists():
            identity['build_manifest'] = json.loads(manifest.read_text())
        result['compilers'][label] = identity
    with tempfile.TemporaryDirectory(prefix='dewy-app-benchmark-') as directory:
        work = Path(directory)
        for name in workloads:
            source = prepare_source(name, work)
            result['measured_harness_sha256'] = prepare_clock(work, clock)
            c_source = work / f'{name}.c'
            shutil.copy2(APPS / c_source.name, c_source)
            binaries = {label: work / f'{name}-{label}' for label in [*variants, 'c']}
            builds = {}
            for label, (compiler, flags) in variants.items():
                _, elapsed = run([compilers[compiler], 'build', source, *flags, '-o', binaries[label]], env)
                builds[label] = elapsed
            _, builds['c'] = run([cc, '-O2', c_source, '-o', binaries['c']], env)
            checksums = {}
            # Fast boundary/small-input comparison before the expensive measurements.
            for size in [0, 1, 17, 1000]:
                checks = {label: execute(binary, size, env)[0] for label, binary in binaries.items()}
                if len(set(checks.values())) != 1:
                    raise RuntimeError(f'{name} count={size}: checksum mismatch {checks}')
                checksums[str(size)] = checks['c']
            size = count if count is not None else COUNTS[name]
            measured = {label: [] for label in binaries}
            labels = list(binaries)
            checksum = None
            for sample in range(samples + 1):
                order = labels if sample % 2 == 0 else labels[::-1]
                for label in order:
                    actual, timing = execute(binaries[label], size, env)
                    if checksum is None:
                        checksum = actual
                    if actual != checksum:
                        raise RuntimeError(f'{name} {label} count={size}: expected {checksum}, got {actual}')
                    if sample:
                        measured[label].append(timing)
            medians = {label: statistics.median(row['kernel_ns'] for row in rows) / 1e6
                       for label, rows in measured.items()}
            result['workloads'][name] = {
                'count': size, 'checksum': checksum, 'preflight_checksums': checksums,
                'source_sha256': digest(APPS / f'{name}.dewy'),
                'adapted_source_sha256': digest(source), 'c_source_sha256': digest(c_source),
                'build_seconds': builds,
                'binary_sha256': {label: digest(binary) for label, binary in binaries.items()},
                'binary_bytes': {label: binary.stat().st_size for label, binary in binaries.items()},
                'samples': measured, 'median_kernel_ms': medians,
                'median_wall_seconds': {label: statistics.median(row['wall_seconds'] for row in rows)
                                        for label, rows in measured.items()},
            }
            print(name + f' ({clock} kernel): ' + ', '.join(
                f'{label} {ms:.2f} ms' for label, ms in medians.items()), flush=True)
    result['load_average_end'] = os.getloadavg()
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--workload', choices=COUNTS, action='append', dest='workloads')
    cli.add_argument('--samples', type=positive, default=5)
    cli.add_argument('--count', type=positive, help='Override the input size for every selected workload')
    cli.add_argument('--cc', default='cc')
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='wall')
    cli.add_argument('--mode', choices=['default', 'release', 'both'], default='release',
                     help='Core build mode; both compares default and release with the same inputs')
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    compilers = {}
    if options.baseline:
        compilers['baseline'] = options.baseline.resolve(strict=True)
    compilers['candidate'] = options.compiler.resolve(strict=True)
    report = measure(compilers, options.workloads or list(COUNTS), options.samples, options.cc,
                     options.count, options.clock, options.mode)
    options.output.write_text(json.dumps(report, indent=2) + '\n')
