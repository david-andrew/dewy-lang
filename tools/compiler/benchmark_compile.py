"""Compare compiler latency with sequential, alternating, warmed measurements."""
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
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKLOADS = {
    'tour-default': ('build', 'examples/tour.dewy'),
    'netpong-default': ('build', 'examples/netpong.dewy'),
    'netpong-web-default': ('build', 'examples/netpong.dewy', '--target', 'wasm'),
    'dunes-default': ('build', 'examples/dunes.dewy'),
    'tour': ('build', 'examples/tour.dewy', '--release'),
    'history': ('build', 'examples/history.dewy', '--release'),
    'exact-rationals': ('build', 'examples/exact_rationals.dewy', '--release'),
    'exact-integers': ('build', 'examples/exact_integers.dewy', '--release'),
    'entities': ('build', 'examples/entities.dewy', '--release'),
    'pool-inventory': ('build', 'examples/pool_inventory.dewy', '--release'),
    'physics-check': ('check', 'examples/physics.dewy'),
    'physics': ('build', 'examples/physics.dewy', '--release'),
    'paddle': ('build', 'examples/paddle.dewy', '--release'),
    'paddle-web': ('build', 'examples/paddle.dewy', '--release', '--target', 'wasm'),
    'forest': ('build', 'examples/forest.dewy', '--release'),
    'forest-web': ('build', 'examples/forest.dewy', '--release', '--target', 'wasm'),
    'dunes': ('build', 'examples/dunes.dewy', '--release'),
    'dunes-web': ('build', 'examples/dunes.dewy', '--release', '--target', 'wasm'),
    'netpong': ('build', 'examples/netpong.dewy', '--release'),
    'netpong-web': ('build', 'examples/netpong.dewy', '--release', '--target', 'wasm'),
    'compiler': ('build', 'compiler/main.jo'),
}


def sample_order(labels: list[str], sample: int) -> list[str]:
    """Balance positions as well as direction when comparing three or more variants."""
    if len(labels) <= 2:
        return labels[:] if sample % 2 == 0 else labels[::-1]
    offset = sample % len(labels)
    order = labels[offset:] + labels[:offset]
    return order if sample // len(labels) % 2 == 0 else order[::-1]


def measure(compilers: dict[str, Path], workloads: list[str], samples: int,
            workers: int, validate: Callable[[str, str, Path], bool] | None = None,
            on_progress: Callable[[dict], None] | None = None) -> dict:
    # Source generators and CLI validators are also imported by Windows tests;
    # only this POSIX CPU-time benchmark needs resource.getrusage.
    import resource

    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = str(workers)
    result = {
        'platform': platform.platform(),
        'cpu_affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
        'load_average_start': os.getloadavg(),
        'workers': workers,
        'samples': samples,
        'warmups_per_compiler': 1,
        'sample_order': 'Alternating for two variants; rotating positions and direction for three or more.',
        'cpu_time_definition': 'User + system CPU seconds for the compiler and its waited-for children; '
                               'may exceed wall time with multiple emission workers.',
        'compilers': {label: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                      for label, path in compilers.items()},
        'workloads': {},
    }
    with tempfile.TemporaryDirectory(prefix='dewy-compile-benchmark-') as directory:
        for name in workloads:
            args = list(WORKLOADS[name])
            source = ROOT / args[1]
            measured = {label: [] for label in compilers}
            cpu_measured = {label: [] for label in compilers}
            output_bytes = {}
            validated = {}
            artifact = None
            if args[0] == 'build':
                args.extend(['-o', str(Path(directory) / name)])
                artifact = Path(directory) / name
                if 'wasm' in args:
                    artifact = artifact.with_suffix('.html')
            labels = list(compilers)
            for sample in range(samples + 1):
                order = sample_order(labels, sample)
                for label in order:
                    cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
                    started = time.perf_counter()
                    run = subprocess.run([str(compilers[label]), *args], cwd=ROOT, env=env,
                                         capture_output=True, text=True, timeout=120, check=False)
                    elapsed = time.perf_counter() - started
                    cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
                    cpu_elapsed = (cpu_after.ru_utime + cpu_after.ru_stime
                                   - cpu_before.ru_utime - cpu_before.ru_stime)
                    if run.returncode:
                        raise RuntimeError(f'{label} {name}:\n{run.stdout}{run.stderr}')
                    if sample:
                        measured[label].append(elapsed)
                        cpu_measured[label].append(cpu_elapsed)
                    if sample == samples and artifact is not None:
                        output_bytes[label] = artifact.stat().st_size
                        if validate is not None:
                            validated[label] = validate(name, label, artifact)
            medians = {label: statistics.median(values) for label, values in measured.items()}
            cpu_medians = {label: statistics.median(values) for label, values in cpu_measured.items()}
            result['workloads'][name] = {
                'arguments': list(WORKLOADS[name]),
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'seconds': measured,
                'median_seconds': medians,
                'cpu_seconds': cpu_measured,
                'median_cpu_seconds': cpu_medians,
                'output_bytes': output_bytes,
                'output_validated': validated,
            }
            print(name + ': ' + ', '.join(f'{label} {elapsed * 1000:.2f} ms wall / '
                                         f'{cpu_medians[label] * 1000:.2f} ms CPU'
                                         for label, elapsed in medians.items()), flush=True)
            if on_progress is not None:
                on_progress(result)
    result['load_average_end'] = os.getloadavg()
    return result


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return number


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--workload', choices=WORKLOADS, action='append', dest='workloads')
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--workers', type=positive, default=1)
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    compilers = {}
    if options.baseline:
        compilers['baseline'] = options.baseline.resolve(strict=True)
    compilers['candidate'] = options.compiler.resolve(strict=True)
    report = measure(compilers, options.workloads or list(WORKLOADS), options.samples, options.workers)
    options.output.write_text(json.dumps(report, indent=2) + '\n')
