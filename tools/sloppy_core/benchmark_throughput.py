"""Measure fresh builds, loaded source volume and compiler phases on real programs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from tools.sloppy_core.benchmark_compile import ROOT, WORKLOADS, positive

SOURCES = re.compile(r'sources: (\d+) files, (\d+) Dewy lines \((\d+) bytes\), '
                     r'(\d+) implementation lines \((\d+) bytes\)')
PHASES = re.compile(r'check ([\d.]+) ms, lower\+codegen ([\d.]+) ms, write ([\d.]+) ms; '
                    r'(\d+) functions, (\d+) nodes, (\d+) bytes of code')
BUILD_WORKLOADS = {key: value for key, value in WORKLOADS.items() if value[0] == 'build'}


def measure(compiler: Path, workloads: list[str], samples: int,
            validate: Callable[[str, Path], None] | None = None) -> dict:
    import resource

    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'platform': platform.platform(),
        'cpu_model': next((line.split(':', 1)[1].strip() for line in
                           Path('/proc/cpuinfo').read_text().splitlines()
                           if line.startswith('model name')), '') if Path('/proc/cpuinfo').exists() else platform.processor(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
        'compiler': {'path': str(compiler), 'sha256': hashlib.sha256(compiler.read_bytes()).hexdigest()},
        'emission_workers': 1,
        'samples': samples,
        'warmups': 1,
        'method': 'Fresh compiler processes and rebuilt output; warm filesystem caches; '
                  'wall and CPU times include process startup, source counting and shutdown.',
        'source_counting': 'Physical loaded source lines, including blanks/comments and unused lazy '
                           'library bodies. Dewy and implementation source are separate. Loaded '
                           'lines/second is input throughput, not fully checked/emitted lines/second. '
                           'Small programs primarily measure latency, not the 250k LOC/s target.',
        'load_average_start': os.getloadavg(),
        'workloads': {},
    }
    with tempfile.TemporaryDirectory(prefix='dewy-throughput-') as directory:
        for name in workloads:
            arguments = list(BUILD_WORKLOADS[name])
            source = ROOT / arguments[1]
            command = [compiler, *arguments, '--time', '-o', Path(directory) / name]
            rows = []
            for sample in range(samples + 1):
                before = resource.getrusage(resource.RUSAGE_CHILDREN)
                start = time.perf_counter()
                ran = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                                     check=True, timeout=120)
                elapsed = time.perf_counter() - start
                after = resource.getrusage(resource.RUSAGE_CHILDREN)
                counts = SOURCES.search(ran.stderr)
                phases = PHASES.search(ran.stderr)
                if counts is None or phases is None:
                    raise RuntimeError(f'Compiler did not report source/phase statistics: {ran.stderr}')
                volumes = dict(zip(('files', 'dewy_lines', 'dewy_bytes', 'implementation_lines',
                                    'implementation_bytes'), map(int, counts.groups()), strict=True))
                row = {'wall_seconds': elapsed,
                       'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                       'check_ms': float(phases[1]), 'lower_codegen_ms': float(phases[2]),
                       'write_ms': float(phases[3])}
                if sample:
                    rows.append(row)
            medians = {key: statistics.median(row[key] for row in rows) for key in rows[0]}
            lines = volumes['dewy_lines'] + volumes['implementation_lines']
            report['workloads'][name] = {
                'arguments': arguments, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'source_counts': volumes, 'samples': rows, 'medians': medians,
                'loaded_lines_per_wall_second': lines / medians['wall_seconds'],
                'loaded_lines_per_cpu_second': lines / medians['cpu_seconds'],
                'functions': int(phases[4]), 'nodes': int(phases[5]), 'code_bytes': int(phases[6]),
            }
            if validate is not None:
                validate(name, Path(directory) / name)
                report['workloads'][name]['output_validated'] = True
            print(f'{name}: {medians["wall_seconds"] * 1000:.1f} ms wall, '
                  f'{medians["cpu_seconds"] * 1000:.1f} ms CPU; {volumes}; '
                  f'phases {medians["check_ms"]:.1f}/{medians["lower_codegen_ms"]:.1f}/'
                  f'{medians["write_ms"]:.1f} ms', flush=True)
    report['load_average_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--workload', choices=BUILD_WORKLOADS, action='append', dest='workloads')
    cli.add_argument('--samples', type=positive, default=5)
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    result = measure(options.compiler.resolve(strict=True),
                     options.workloads or ['tour-default', 'netpong-default', 'dunes-default', 'compiler'],
                     options.samples)
    options.output.write_text(json.dumps(result, indent=2) + '\n')
