"""Measure exact bigint arithmetic and decimal I/O, optionally against an older core."""
from __future__ import annotations

import argparse
import json
import math
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
MODULUS = 1000000007
NUMERATOR = 2**511 + 2**255 + 12345
DIVISOR = 2**253 + 54321
TEXT_VALUE = 2**2048 + 43
KERNELS = {
    'factorial150': '''loop i in [0..count) {
        let value=bigint(1)
        loop n in [2..151) {value=value*n}
        let word=(value%1000000007).to_int64()
        if word is? none panic("checksum conversion")
        checksum=(checksum+word)%1000000007
    }''',
    'division512': '''loop i in [0..count) {
        let parts=(numerator+i).divmod(divisor)
        let word=((parts.quotient+parts.remainder)%1000000007).to_int64()
        if word is? none panic("checksum conversion")
        checksum=(checksum+word)%1000000007
    }''',
    'decimal2048': '''loop i in [0..count) {
        let text="{decimal}"
        let parsed=bigint(text)
        if parsed not=? decimal panic("decimal round trip")
        checksum=(checksum+text.length)%1000000007
    }''',
}


def expected(name: str, count: int) -> int:
    if name == 'factorial150':
        return math.factorial(150) * count % MODULUS
    if name == 'division512':
        return sum(sum(divmod(NUMERATOR + i, DIVISOR)) for i in range(count)) % MODULUS
    return len(str(TEXT_VALUE)) * count % MODULUS


def measure(compilers: dict[str, Path], samples: int, count: int) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'platform': platform.platform(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'compilers': {label: {'path': str(path), 'sha256': digest(path),
                             'library_sha256': digest(path.parent.parent / 'lib/bigint.dewy')}
                      for label, path in compilers.items()},
        'samples': samples, 'count': count, 'warmups': 1, 'flags': ['--release'],
        'load_average_start': os.getloadavg(),
        'limits': ['Native host; sequential alternating runs; shared desktop.',
                   'Independent Python result checks at 0, 1, 17 and measured iteration counts.',
                   'Kernel includes arithmetic, owned allocations and checksums; excludes process startup.',
                   'Decimal kernel includes format, parse, comparison and grapheme length.',
                   'Optional baseline compares compiler/library revisions, not another language runtime.'],
        'sources': {}, 'validation': {}, 'build_seconds': {}, 'measurements': {},
    }
    with tempfile.TemporaryDirectory(prefix='dewy-bigint-benchmark-') as directory:
        work = Path(directory)
        shutil.copy2(ROOT / 'tools/sloppy_core/benchmark_harness.jo', work / 'harness.jo')
        report['sources']['harness.jo'] = (work / 'harness.jo').read_text()
        for name, kernel in KERNELS.items():
            source = work / f'{name}.dewy'
            source.write_text(f'''from bigint import bigint
from p"harness.jo" import size_argument
main=():>void=>{{
    let count=size_argument(args() {count})
    let numerator=bigint("{NUMERATOR}")
    let divisor=bigint("{DIVISOR}")
    let decimal=bigint("{TEXT_VALUE}")
    let checksum:int64=0
    let start=time_ns()
    {kernel}
    let elapsed=time_ns()-start
    printl"{{checksum}} {{elapsed}}"
}}
''')
            report['sources'][source.name] = source.read_text()
            binaries = {}
            report['measurements'][name] = {}
            report['validation'][name] = {}
            report['build_seconds'][name] = {}
            for label, compiler in compilers.items():
                binary = work / f'{name}-{label}'
                _, elapsed = run([str(compiler), 'build', str(source), '--release', '-o', str(binary)], env)
                binaries[label] = binary
                report['build_seconds'][name][label] = elapsed
                report['validation'][name][label] = {}
                for size in [0, 1, 17]:
                    actual, _ = execute(binary, size, env)
                    if actual != expected(name, size):
                        raise RuntimeError(f'{name}/{label}, count {size}: {actual} != {expected(name, size)}')
                    report['validation'][name][label][size] = actual
                report['measurements'][name][label] = []
            expected_result = expected(name, count)
            for sample in range(samples + 1):
                order = list(compilers) if sample % 2 == 0 else list(reversed(compilers))
                for label in order:
                    actual, times = execute(binaries[label], count, env)
                    if actual != expected_result:
                        raise RuntimeError(f'{name}/{label}: {actual} != {expected_result}')
                    report['validation'][name][label][count] = actual
                    if sample:
                        report['measurements'][name][label].append(times)
        report['median_kernel_ms'] = {
            name: {label: statistics.median(row['kernel_ns'] for row in rows) / 1e6
                   for label, rows in results.items()}
            for name, results in report['measurements'].items()}
    report['load_average_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--count', type=positive, default=2000)
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    selected = {'candidate': options.compiler.resolve(strict=True)}
    if options.baseline:
        selected = {'baseline': options.baseline.resolve(strict=True), **selected}
    result = measure(selected, options.samples, options.count)
    options.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['median_kernel_ms'], indent=2))
