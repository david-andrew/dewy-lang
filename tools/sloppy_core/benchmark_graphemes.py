"""Compare full and early-exit Dewy string loops, including live loop allocations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import tempfile
from pathlib import Path

from tools.sloppy_core.benchmark_apps import digest, run
from tools.sloppy_core.benchmark_compile import positive

ROOT = Path(__file__).resolve().parents[2]
# unit, number of units, maximum visited clusters, repetitions
WORKLOADS = {
    'ascii-full': ('a', 100000, 100000, 10),
    'unicode-full': ('é👩‍👩‍👧‍👦🇺🇸', 10000, 30000, 10),
    'ascii-prefix-small': ('a', 1000, 1, 20),
    'ascii-prefix-large': ('a', 100000, 1, 20),
}
SOURCE = '''from p"support.jo" import byte_length
scan=(text:string limit:int64):>int64=>{
    let sum:int64=0
    let count:int64=0
    loop c in text {
        sum+=byte_length(c)
        count+=1
        if count >=? limit break
    }
    return sum
}
loop_allocations=(text:string):>int64=>{
    let before=alloc_count()
    loop c in text return alloc_count()-before
    return 0
}
main=()=>{
    let text=repeat(UNIT SIZE)
    let live=loop_allocations(text)
    let started=time_ns()
    let checksum:int64=0
    loop iteration in [0..REPEATS) {checksum+=scan(text LIMIT)}
    let elapsed=time_ns()-started
    printl"{checksum} {elapsed} {live}"
}
'''


def measure(compilers: dict[str, Path], samples: int) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'platform': platform.platform(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
        'load_average_start': os.getloadavg(),
        'samples': samples,
        'warmups': 1,
        'compilers': {},
        'workloads': {},
        'limits': ['Native release, one emission worker, warm filesystem caches.',
                   'Kernel excludes input construction; wall time includes the whole process.',
                   'Live allocation delta is measured in the first loop body; it is not RSS or total allocations.',
                   'Each iteration yields an independent string; this is not zero-copy iteration.'],
    }
    for label, compiler in compilers.items():
        identity = {'path': str(compiler), 'sha256': digest(compiler)}
        manifest = compiler.parent.parent / 'build.json'
        if manifest.exists():
            identity['build_manifest'] = json.loads(manifest.read_text())
        report['compilers'][label] = identity
    with tempfile.TemporaryDirectory(prefix='dewy-grapheme-benchmark-') as directory:
        work = Path(directory)
        support = 'byte_length = (text: str) -> int: len(text)\n'
        (work / 'support.jo').write_text(support)
        report['support_source'] = support
        for name, (unit, size, limit, repeats) in WORKLOADS.items():
            source = work / f'{name}.dewy'
            source.write_text(SOURCE.replace('UNIT', json.dumps(unit, ensure_ascii=False))
                              .replace('SIZE', str(size)).replace('LIMIT', str(limit))
                              .replace('REPEATS', str(repeats)))
            binaries = {label: work / f'{name}-{label}' for label in compilers}
            builds = {}
            for label, compiler in compilers.items():
                _, builds[label] = run([compiler, 'build', source, '--release', '-o', binaries[label]], env)
            expected = repeats if limit == 1 else len(unit.encode()) * size * repeats
            measured = {label: [] for label in compilers}
            labels = list(compilers)
            for sample in range(samples + 1):
                for label in (labels if sample % 2 == 0 else labels[::-1]):
                    output, wall = run([binaries[label]], env)
                    checksum, ns, allocations = map(int, output.split())
                    if checksum != expected or ns < 0 or allocations < 0:
                        raise RuntimeError(f'{name} {label}: unexpected result {output!r}; expected {expected}')
                    if sample:
                        measured[label].append({'kernel_ns': ns, 'wall_seconds': wall,
                                                'live_loop_allocations': allocations})
            medians = {label: {key: statistics.median(value[key] for value in values)
                               for key in values[0]} for label, values in measured.items()}
            report['workloads'][name] = {'source': source.read_text(), 'source_sha256': digest(source),
                                         'expected_checksum': expected, 'build_seconds': builds,
                                         'measurements': measured, 'medians': medians}
            print(name + ': ' + ', '.join(f'{label} {value["kernel_ns"] / 1e6:.3f} ms, '
                  f'{value["live_loop_allocations"]} live allocations'
                  for label, value in medians.items()), flush=True)
    report['load_average_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--samples', type=positive, default=5)
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    compilers = {}
    if options.baseline:
        compilers['baseline'] = options.baseline.resolve(strict=True)
    compilers['candidate'] = options.compiler.resolve(strict=True)
    options.output.write_text(json.dumps(measure(compilers, options.samples), indent=2) + '\n')
