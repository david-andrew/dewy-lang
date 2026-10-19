"""Paired native JSON parsing workloads with independent value checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tools.sloppy_core.benchmark_compile import sample_order
from tools.sloppy_core.benchmark_regex import CLOCK, quote
from tools.sloppy_core.performance_gate import compare_samples, save_report, toolchain_identity


# Plain/escaped text, small calls, realistic objects and non-string controls.
WORKLOADS = {
    'plain-string': ('level_asset_' * 1024, 500),
    'escaped-string': ('level path\\name\n' * 512, 300),
    'short-object': ({'name': 'player', 'enabled': True, 'target': None, 'layer': 3}, 5000),
    'objects': ([{'name': f'entity_{i:04}', 'enabled': bool(i % 2),
                  'position': [i, i + 1, i + 2]} for i in range(128)], 100),
    'keywords': ([True, False, None] * 256, 200),
    'numbers': ([i * 0.125 for i in range(256)], 200),
}


def prepare(value, count: int) -> tuple[str, str, int]:
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, str):
        read = 'len(parsed.as_str() ?? "")'
    elif isinstance(value, list):
        read = 'parsed.as_list().length'
    else:
        read = 'parsed.keys().length'
    source = ('from p"clock.jo" import clock\nmain=()=>{\n'
              + f'let text={quote(text)}\nlet probe=parse_json(text)\n'
              + 'if probe is? JsonError return 1\nprintl(to_json(probe))\n'
              + 'let checksum:int64=0\nlet start=clock()\n'
              + f'loop i in [0..{count}) {{let parsed=parse_json(text)\n'
              + f'if parsed is? JsonError return 2\nchecksum+={read}\n}}\n'
              + 'let elapsed=clock()-start\nprintl"{checksum} {elapsed}"\nreturn 0\n}\n')
    return source, text, count * len(value)


def measure(compilers: dict[str, Path], output: Path, samples: int = 7,
            divisor: int = 1) -> dict:
    if samples < 7 or divisor < 1:
        raise ValueError('Use at least seven samples and a positive iteration divisor')
    compilers = {k: v.resolve(strict=True) for k, v in compilers.items()}
    identities = {k: toolchain_identity(v) for k, v in compilers.items()}
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {'status': 'incomplete', 'toolchains': identities, 'samples': samples,
              'warmups': 1, 'cpu_affinity': sorted(os.sched_getaffinity(0)),
              'iteration_divisor': divisor,
              'clock': 'Thread CPU seconds; parsing, result allocation/destruction and '
                       'a size checksum included. Source construction and independent '
                       'serialization/value check excluded.',
              'clock_source_sha256': hashlib.sha256(CLOCK.encode()).hexdigest(),
              'workloads': {}}
    with tempfile.TemporaryDirectory(prefix='dewy-json-benchmark-') as temporary:
        directory = Path(temporary)
        (directory / 'clock.jo').write_text(CLOCK)
        for name, (value, default_count) in WORKLOADS.items():
            count = max(1, default_count // divisor)
            source, text, expected = prepare(value, count)
            path = directory / 'main.dewy'
            path.write_text(source)
            workload = {'input_utf8_bytes': len(text.encode()), 'iterations': count,
                        'expected_checksum': expected,
                        'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                        'input_sha256': hashlib.sha256(text.encode()).hexdigest(), 'modes': {}}
            report['workloads'][name] = workload
            for mode in ('default', 'release'):
                binaries = {}
                for label, compiler in compilers.items():
                    binary = directory / label
                    binaries[label] = binary
                    command = [compiler, 'build', path, '-o', binary]
                    if mode == 'release':
                        command.append('--release')
                    built = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
                    if built.returncode:
                        raise RuntimeError(built.stdout + built.stderr)
                times = {k: [] for k in compilers}
                for sample in range(samples + 1):
                    for label in sample_order(list(compilers), sample):
                        ran = subprocess.run([binaries[label]], env=env, capture_output=True,
                                             text=True, timeout=30, check=True)
                        rendered, measurement = ran.stdout.strip().splitlines()
                        checksum, ns = map(int, measurement.split())
                        if json.loads(rendered) != value or checksum != expected or ns < 0:
                            raise RuntimeError(f'{name}/{mode}/{label}: incorrect JSON result or timing')
                        if sample:
                            times[label].append(ns / 1e9)
                comparison = compare_samples(times['control'], times['candidate'])
                workload['modes'][mode] = {
                    'cpu_seconds': times, 'comparison': comparison,
                    'binary_sha256': {k: hashlib.sha256(v.read_bytes()).hexdigest()
                                      for k, v in binaries.items()},
                }
                save_report(output, report)
                print(f'{name}/{mode}: {comparison}', flush=True)
    if identities != {k: toolchain_identity(v) for k, v in compilers.items()}:
        raise RuntimeError('A toolchain changed during measurement')
    report['status'] = 'complete'
    save_report(output, report)
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--core', required=True, type=Path)
    cli.add_argument('--baseline', required=True, type=Path)
    cli.add_argument('--json', required=True, type=Path)
    cli.add_argument('--samples', type=int, default=7)
    cli.add_argument('--cpu', type=int, default=1)
    cli.add_argument('--iteration-divisor', type=int, default=1,
                     help='shorten harness smoke checks; do not use for performance acceptance')
    args = cli.parse_args()
    os.sched_setaffinity(0, {args.cpu})
    measure({'control': args.baseline, 'candidate': args.core}, args.json,
            args.samples, args.iteration_divisor)
