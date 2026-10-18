"""Measure independent callback arguments with alternating fresh-process samples."""
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

from tools.sloppy_core.benchmark_compile import positive

ROOT = Path(__file__).resolve().parents[2]
PRELUDE = '''Counter:type=():>int64
make=()=>{let n=0 return ()=>{n+=1; n}}
'''
WORKLOADS = {
    'counter': ('''twice=(f:Counter)=>f()+f()
main=()=>{let a=make() let sum=0
loop i in [0..2000000) {sum+=twice(a)}
printl(sum) printl(a())}
''', '6000000\n1\n'),
    'record': ('''Box:type=[left:Counter right:Counter]
read=(box:Box)=>box.left()+box.right()
main=()=>{let box=Box[make() make()] let sum=0
loop i in [0..1000000) {sum+=read(box)}
printl(sum) printl(box.left()) printl(box.right())}
''', '2000000\n1\n1\n'),
    'array': ('''read=(xs:array<Counter>)=>xs[0]()+xs[1]()+xs[2]()+xs[3]()
main=()=>{let xs=[make() make() make() make()] let sum=0
loop i in [0..500000) {sum+=read(xs)}
printl(sum) printl(xs[0]()) printl(xs[3]())}
''', '2000000\n1\n1\n'),
}


def measure(compilers: dict[str, Path], samples: int) -> dict:
    import resource

    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'platform': platform.platform(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
        'compilers': {label: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                      for label, path in compilers.items()},
        'samples': samples,
        'warmups': 1,
        'load_average_start': os.getloadavg(),
        'cpu_time_definition': 'User plus system CPU seconds of each fresh native process.',
        'workloads': {},
    }
    with tempfile.TemporaryDirectory(prefix='dewy-callback-benchmark-') as directory:
        work = Path(directory)
        for name, (body, expected) in WORKLOADS.items():
            source = work / f'{name}.dewy'
            source.write_text(PRELUDE + body)
            result = {'source': source.read_text(), 'expected': expected, 'modes': {}}
            report['workloads'][name] = result
            for mode in ('default', 'release'):
                binaries = {}
                for label, compiler in compilers.items():
                    binary = work / f'{name}-{mode}-{label}'
                    subprocess.run([compiler, 'build', source, '-o', binary,
                                    *(['--release'] if mode == 'release' else [])],
                                   env=env, capture_output=True, text=True, check=True, timeout=30)
                    binaries[label] = binary
                measurements = {label: [] for label in compilers}
                for sample in range(samples + 1):
                    labels = list(compilers)
                    for label in labels if sample % 2 == 0 else labels[::-1]:
                        before = resource.getrusage(resource.RUSAGE_CHILDREN)
                        start = time.perf_counter()
                        ran = subprocess.run([binaries[label]], capture_output=True, text=True,
                                             check=True, timeout=30, env=env)
                        elapsed = time.perf_counter() - start
                        after = resource.getrusage(resource.RUSAGE_CHILDREN)
                        if ran.stdout != expected:
                            raise RuntimeError(f'{name}/{mode}/{label}: {ran.stdout!r} != {expected!r}')
                        if sample:
                            measurements[label].append({
                                'wall_seconds': elapsed,
                                'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                            })
                medians = {label: {key: statistics.median(row[key] for row in rows)
                                   for key in ('wall_seconds', 'cpu_seconds')}
                           for label, rows in measurements.items()}
                result['modes'][mode] = {'samples': measurements, 'medians': medians}
                print(name, mode, medians, flush=True)
    report['load_average_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path, required=True)
    cli.add_argument('--samples', type=positive, default=5)
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    result = measure({'baseline': options.baseline.resolve(strict=True),
                      'candidate': options.compiler.resolve(strict=True)}, options.samples)
    options.output.write_text(json.dumps(result, indent=2) + '\n')
