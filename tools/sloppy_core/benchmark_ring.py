"""Compare the Dewy ring example with the same algorithm in the core's implementation language."""
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

from tools.sloppy_core.benchmark_apps import digest, execute, run
from tools.sloppy_core.benchmark_compile import positive

ROOT = Path(__file__).resolve().parents[2]
JO_RING = '''struct Ring[T]:
    capacity: int
    values: T[]
    head = 0
new_ring[T] = (capacity: int) -> Ring[T]:
    if capacity <= 0: panic("ring capacity must be positive")
    Ring[T](capacity = capacity)
len[T] = (ring: Ring[T]) -> int: ring.values.len()
push[T] = (ring: mut Ring[T], value: T):
    if ring.values.len() < ring.capacity:
        ring.values.push(value)
    else:
        ring.values[ring.head] = value
        ring.head += 1
        if ring.head == ring.capacity: ring.head = 0
storage_index[T] = (ring: Ring[T], index: int) -> int:
    if index < 0 or index >= ring.values.len(): panic("ring index out of bounds")
    slot = ring.head + index
    if slot >= ring.capacity: slot - ring.capacity else: slot
([])[T] = (ring: Ring[T], index: int) -> T: ring.values[storage_index(ring, index)]
([]=)[T] = (ring: mut Ring[T], index: int, value: T):
    ring.values[storage_index(ring, index)] = value
'''
DEWY_MAIN = '''from p"ring.dewy" import new_ring
from p"harness.jo" import size_argument
main=():>void=>{
    let count=size_argument(args() 10000000)
    let ring=new_ring<int64>(1024)
    let start=time_ns()
    loop i in [0..count) {ring.push(i)}
    let checksum:int64=0
    loop i in [0..ring.len()) {checksum+=ring[i]}
    let elapsed=time_ns()-start
    printl"{checksum} {elapsed}"
}
'''
JO_MAIN = '''use "ring.jo"
use "harness.jo"
main = ():
    count = size_argument(args(), 10000000)
    ring = new_ring[int](1024)
    start = time_ns()
    loop i in [0..count): ring.push(i)
    checksum = 0
    loop i in [0..ring.len()): checksum += ring[i]
    elapsed = time_ns() - start
    print("{checksum} {elapsed}")
'''


def checksum(count: int) -> int:
    held = min(count, 1024)
    return held * (2 * count - held - 1) // 2


def measure(compiler: Path, samples: int, count: int) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'platform': platform.platform(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'compiler': {'path': str(compiler), 'sha256': digest(compiler)},
        'samples': samples, 'count': count, 'capacity': 1024, 'warmups': 1,
        'flags': ['--release'], 'load_average_start': os.getloadavg(),
        'limits': ['Native host; sequential alternating runs; no graphics.',
                   'The .jo baseline is a manual translation of the same ring algorithm, not C.',
                   'Kernel includes insertion, growth and final indexed checksum; excludes process startup.',
                   'Timing covers scalar elements with no retained copies during mutation.'],
        'sources': {}, 'validation': {}, 'build_seconds': {}, 'measurements': {},
    }
    with tempfile.TemporaryDirectory(prefix='dewy-ring-benchmark-') as directory:
        work = Path(directory)
        shutil.copy2(ROOT / 'examples/sloppy_core/ring.dewy', work / 'ring.dewy')
        shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', work / 'harness.jo')
        (work / 'ring.jo').write_text(JO_RING)
        (work / 'main.dewy').write_text(DEWY_MAIN)
        (work / 'main.jo').write_text(JO_MAIN)
        report['sources'] = {p.name: p.read_text() for p in sorted(work.iterdir())}
        binaries = {}
        for label in ['dewy', 'jo']:
            binary = work / f'ring-{label}'
            _, elapsed = run([str(compiler), 'build', str(work / f'main.{label}'),
                              '--release', '-o', str(binary)], env)
            binaries[label] = binary
            report['build_seconds'][label] = elapsed
            report['validation'][label] = {}
            for size in [0, 1, 17, 1024, 1025, 10000]:
                actual, _ = execute(binary, size, env)
                if actual != checksum(size):
                    raise RuntimeError(f'{label}, count {size}: {actual} != {checksum(size)}')
                report['validation'][label][size] = actual
            report['measurements'][label] = []
        for sample in range(samples + 1):
            order = ['dewy', 'jo'] if sample % 2 == 0 else ['jo', 'dewy']
            for label in order:
                actual, times = execute(binaries[label], count, env)
                if actual != checksum(count):
                    raise RuntimeError(f'{label}: {actual} != {checksum(count)}')
                if sample:
                    report['measurements'][label].append(times)
        report['median_kernel_ms'] = {
            label: statistics.median(row['kernel_ns'] for row in rows) / 1e6
            for label, rows in report['measurements'].items()}
    report['load_average_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--count', type=positive, default=10000000)
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    result = measure(options.compiler.resolve(strict=True), options.samples, options.count)
    options.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['median_kernel_ms'], indent=2))
