"""Measure managed Pool item updates, with an independent retained snapshot."""
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
SOURCE = ROOT / 'examples/pool_inventory.dewy'


def checksum(count: int) -> int:
    amounts = [[0] * 32 for _ in range(64)]
    for update in range(count):
        amounts[update % 64][update // 64 % 32] += update % 7 + 1
    result = 3
    for inventory in amounts:
        for amount in inventory:
            result = (result * 31 + amount) % 1000000007
    return result


def measure(compilers: dict[str, Path], count: int, samples: int) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    source = SOURCE.read_bytes()
    result = {
        'platform': platform.platform(), 'count': count, 'samples': samples,
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
        'source': source.decode(), 'source_sha256': hashlib.sha256(source).hexdigest(),
        'flags': ['--release'], 'workers': 1, 'warmups_per_binary': 1,
        'load_average_start': os.getloadavg(), 'compilers': {},
        'limits': ['Native host; one build per compiler; alternating warmed execution.',
                   '64 entities with 32 integer inventory slots each; a snapshot remains live.',
                   'Kernel timing excludes construction and checksums; wall time includes them.',
                   'Python independently checks final values and the unchanged snapshot.'],
    }
    snapshot = checksum(0)
    expected = {size: checksum(size) for size in {0, 1, 17, 1000, count}}
    result['expected_checksums'] = expected
    result['snapshot_checksum'] = snapshot
    with tempfile.TemporaryDirectory(prefix='dewy-pool-benchmark-') as directory:
        binaries = {}
        for label, compiler in compilers.items():
            binary = Path(directory) / label
            started = time.perf_counter()
            built = subprocess.run([compiler, 'build', SOURCE, '--release', '-o', binary],
                                   cwd=ROOT, env=env, capture_output=True, text=True,
                                   timeout=120, check=False)
            elapsed = time.perf_counter() - started
            if built.returncode:
                raise RuntimeError(f'{label}:\n{built.stdout}{built.stderr}')
            manifest = compiler.parent.parent / 'build.json'
            result['compilers'][label] = {
                'path': str(compiler), 'sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
                'build_seconds': elapsed, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'manifest': json.loads(manifest.read_text()) if manifest.exists() else None,
            }
            binaries[label] = binary

        def execute(label: str, size: int) -> dict:
            started = time.perf_counter()
            ran = subprocess.run([binaries[label], str(size)], env=env, capture_output=True,
                                 text=True, timeout=120, check=False)
            elapsed = time.perf_counter() - started
            if ran.returncode:
                raise RuntimeError(f'{label}:\n{ran.stdout}{ran.stderr}')
            actual, saved, ns = map(int, ran.stdout.split())
            if actual != expected[size] or saved != snapshot or ns < 0:
                raise RuntimeError(f'{label} count={size}: invalid result {ran.stdout!r}')
            return {'kernel_ns': ns, 'wall_seconds': elapsed}

        for size in [0, 1, 17, 1000]:
            for label in binaries:
                execute(label, size)
        measured = {label: [] for label in binaries}
        labels = list(binaries)
        for sample in range(samples + 1):
            order = labels if sample % 2 == 0 else labels[::-1]
            for label in order:
                timing = execute(label, count)
                if sample:
                    measured[label].append(timing)
        result['measurements'] = measured
        result['median_kernel_ms'] = {
            label: statistics.median(row['kernel_ns'] for row in rows) / 1e6
            for label, rows in measured.items()
        }
    result['load_average_end'] = os.getloadavg()
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--count', type=positive, default=1000000)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    compilers = {}
    if args.baseline:
        compilers['baseline'] = args.baseline.resolve(strict=True)
    compilers['candidate'] = args.compiler.resolve(strict=True)
    result = measure(compilers, args.count, args.samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    for label, value in result['median_kernel_ms'].items():
        print(f'{label}: {value:.2f} ms kernel')
