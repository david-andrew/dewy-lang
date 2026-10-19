"""Paired native regex workloads, including short inputs and pattern preparation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from tools.sloppy_core.benchmark_compile import sample_order
from tools.sloppy_core.performance_gate import compare_samples, save_report, toolchain_identity


WORKLOADS = {
    'long-negative': ('[a-z]+[0-9]+', 'alphabet ' * 256, 'contains', 1000),
    'long-class': ('[a-z ]+', 'alphabet ' * 256, 'matches', 1000),
    'long-captures': ('([a-z]+)([0-9]+)', 'x ' * 1024 + 'word123', 'find', 1000),
    'long-unicode': ('[^é]+!', 'é日' * 200 + '日本語!', 'find', 1000),
    'line-anchors': ('^item [0-9]+$', 'ignore\n' * 256 + 'item 42', 'find', 1000),
    'short-reused': ('([a-z]+)([0-9]+)', 'item123', 'find', 5000),
    'short-prepare': ('([a-z]+)([0-9]+)', 'item123', 'prepare', 2000),
}
CLOCK = '''clock = () -> int:
    ts: (int, int)
    if syscall(228, 3, &ts) != 0: panic("thread CPU clock unavailable")
    ts.0 * 1000000000 + ts.1
'''


def quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False).replace('{', r'\{').replace('}', r'\}')


def prepare(pattern: str, text: str, operation: str, count: int) -> tuple[str, int]:
    if operation in ('contains', 'matches'):
        search = re.search if operation == 'contains' else re.fullmatch
        expected = count * int(search(pattern, text, re.MULTILINE) is not None)
        body = f'if text.{operation}(r) {{checksum+=1}}'
    else:
        match = re.search(pattern, text, re.MULTILINE)
        assert match is not None
        # Match offsets are bytes; Dewy string lengths are graphemes. Every
        # character in these fixed inputs is a separate grapheme.
        expected = count * (len(text[:match.start()].encode()) + len(text[:match.end()].encode())
                            + len(match.group()) + sum(len(g or '') for g in match.groups()))
        body = ('let found=text.find(r)\nif found is?none return 2\n'
                'checksum+=found.start+found.end+len(found.text)\n'
                'loop group in found.groups {checksum+=len(group)}')
    setup = f'let text={quote(text)}\n'
    if operation == 'prepare':
        body = f'let r=regex({quote(pattern)})\n' + body
    else:
        setup += f'let r=regex({quote(pattern)})\n'
    source = ('from p"clock.jo" import clock\nmain=()=>{\n' + setup
              + 'let checksum:int64=0\nlet start=clock()\n'
              + f'loop i in [0..{count}) {{\n' + body
              + '\n}\nlet elapsed=clock()-start\nprintl"{checksum} {elapsed}"\nreturn 0\n}\n')
    return source, expected


def measure(compilers: dict[str, Path], output: Path, samples: int = 7,
            divisor: int = 1) -> dict:
    if samples < 7 or divisor < 1:
        raise ValueError('Use at least seven samples and a positive iteration divisor')
    compilers = {k: v.resolve(strict=True) for k, v in compilers.items()}
    identities = {k: toolchain_identity(v) for k, v in compilers.items()}
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'status': 'incomplete', 'toolchains': identities, 'samples': samples, 'warmups': 1,
        'cpu_affinity': sorted(os.sched_getaffinity(0)), 'iteration_divisor': divisor,
        'clock': 'Thread CPU seconds; matching, matcher setup and result allocation included. '
                 'Input/Regex construction excluded except short-prepare, which includes regex().',
        'clock_source_sha256': hashlib.sha256(CLOCK.encode()).hexdigest(), 'workloads': {},
    }
    with tempfile.TemporaryDirectory(prefix='dewy-regex-benchmark-') as temporary:
        directory = Path(temporary)
        (directory / 'clock.jo').write_text(CLOCK)
        for name, (pattern, text, operation, default_count) in WORKLOADS.items():
            count = max(1, default_count // divisor)
            source, expected = prepare(pattern, text, operation, count)
            path = directory / 'main.dewy'
            path.write_text(source)
            workload = {
                'pattern': pattern, 'input_utf8_bytes': len(text.encode()), 'operation': operation,
                'iterations': count, 'expected_checksum': expected,
                'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'modes': {},
            }
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
                        checksum, ns = map(int, ran.stdout.strip().split())
                        if checksum != expected:
                            raise RuntimeError(f'{name}/{mode}/{label}: {checksum} != {expected}')
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
                     help='shorten harness smoke checks; do not use these for performance acceptance')
    args = cli.parse_args()
    os.sched_setaffinity(0, {args.cpu})
    measure({'control': args.baseline, 'candidate': args.core}, args.json,
            args.samples, args.iteration_divisor)
