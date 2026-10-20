"""Diagnostic instruction comparisons against fixed and previous compiler bundles.

Counts help locate extra compiler work; they do not certify elapsed-time or
runtime performance. Linux hardware counters are required; no fallback changes
the libraries, source workload or measurement method.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shlex
import statistics
import subprocess
import tempfile
from pathlib import Path

from tools.compiler.benchmark_compile import ROOT, WORKLOADS, positive, sample_order
from tools.compiler.performance_gate import REFERENCE, save_report, toolchain_identity, tree_digest

NAMES = ('throughput-default', 'throughput-release', 'tour-default',
         'netpong-default', 'dunes-default', 'compiler-reference')
COUNTER = Path(__file__).with_name('count_instructions.c')


def counter_result(stderr: str) -> dict:
    """Reject unavailable/multiplexed counters rather than scale partial counts."""
    try:
        row = json.loads(stderr.splitlines()[-1])
    except (ValueError, IndexError) as error:
        raise ValueError('Missing hardware instruction count') from error
    keys = ('instructions', 'enabled_ns', 'running_ns')
    if not isinstance(row, dict) or any(type(row.get(k)) is not int or row[k] <= 0 for k in keys):
        raise ValueError('Invalid hardware instruction count')
    if row['enabled_ns'] != row['running_ns']:
        raise ValueError('Multiplexed hardware instruction count')
    return {k: row[k] for k in keys}


def measure(reference: Path, previous: Path, candidate: Path, output: Path,
            samples: int = 3, workloads: list[str] | None = None) -> dict:
    from tools.compiler.benchmark_sloppy import generate_dewy

    if samples < 1:
        raise ValueError('At least one instruction sample is required')
    names = list(NAMES) if workloads is None else workloads
    if not names or set(names) - set(NAMES):
        raise ValueError('Select at least one supported instruction workload')
    compilers = {k: p.resolve(strict=True) for k, p in
                 [('reference', reference), ('previous', previous), ('candidate', candidate)]}
    identities = {k: toolchain_identity(p) for k, p in compilers.items()}
    pinned = json.loads(REFERENCE.read_text())
    for key in ('compiler_sources_sha256', 'library_sha256'):
        if identities['reference'][key] != pinned[key]:
            raise ValueError(f'Reference {key} does not match the pinned stage')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    source_tree = tree_digest(ROOT / 'examples')
    counter_hash = hashlib.sha256(COUNTER.read_bytes()).hexdigest()
    report = {'status': 'incomplete', 'kind': 'instruction-diagnostic',
              'limits': 'Instruction counts do not establish latency, runtime parity or stage acceptance.',
              'reference_stage': pinned, 'toolchains': identities,
              'compiler_paths': {k: str(p) for k, p in compilers.items()},
              'samples': samples, 'warmups_per_compiler': 1, 'workers': 1,
              'platform': platform.platform(), 'cpu_affinity': sorted(os.sched_getaffinity(0)),
              'example_tree_sha256': source_tree, 'counter_source_sha256': counter_hash,
              'workloads': {}}
    save_report(output, report)
    with tempfile.TemporaryDirectory(prefix='dewy-instructions-') as temporary:
        directory = Path(temporary)
        counter = directory / 'count-instructions'
        subprocess.run([*shlex.split(os.environ.get('CC', 'cc')), '-O2', '-Wall', '-Wextra',
                        COUNTER, '-o', counter], capture_output=True, text=True, check=True, timeout=30)
        source = directory / 'large.dewy'
        source.write_text(generate_dewy(2000))
        arguments = {name: WORKLOADS[name] for name in NAMES if name in WORKLOADS}
        arguments.update({'throughput-default': ('build', str(source)),
                          'throughput-release': ('build', str(source), '--release'),
                          'compiler-reference': ('build', str(compilers['reference'].parent.parent / 'compiler/main.jo'))})
        for name in names:
            args = arguments[name]
            source_path = ROOT / args[1]
            artifact = directory / 'program'
            rows = {k: [] for k in compilers}
            checked = {}
            for sample in range(samples + 1):
                for label in sample_order(list(compilers), sample):
                    run = subprocess.run([counter, compilers[label], *args, '-o', artifact],
                                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
                    if run.returncode:
                        raise RuntimeError(f'{name}/{label}: {run.stdout}{run.stderr}')
                    row = counter_result(run.stderr)
                    if sample:
                        rows[label].append(row)
                    if sample == samples and name.startswith('throughput-'):
                        ran = subprocess.run([artifact], env=env, capture_output=True,
                                             text=True, check=True, timeout=30)
                        value = float(ran.stdout.strip())
                        if not math.isclose(value, 102380577.8970889, rel_tol=1e-12):
                            raise ValueError(f'{name}/{label}: incorrect generated-program result')
                        checked[label] = value
            medians = {k: statistics.median(r['instructions'] for r in rs) for k, rs in rows.items()}
            ratios = {k: medians['candidate'] / medians[k] for k in ('reference', 'previous')}
            report['workloads'][name] = {
                'arguments': list(args), 'source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
                'samples': rows, 'median_instructions': medians, 'candidate_ratios': ratios,
                'validated_outputs': checked,
            }
            save_report(output, report)
            print(f'{name}: {medians["candidate"]:,.0f} instructions; '
                  + ', '.join(f'{v:.6f}x {k}' for k, v in ratios.items()), flush=True)
    if identities != {k: toolchain_identity(p) for k, p in compilers.items()}:
        raise ValueError('Toolchain changed during instruction measurement')
    if source_tree != tree_digest(ROOT / 'examples'):
        raise ValueError('Application sources changed during instruction measurement')
    if counter_hash != hashlib.sha256(COUNTER.read_bytes()).hexdigest():
        raise ValueError('Counter source changed during instruction measurement')
    report['status'] = 'complete'
    save_report(output, report)
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--reference', required=True, type=Path)
    cli.add_argument('--previous', required=True, type=Path)
    cli.add_argument('--candidate', required=True, type=Path)
    cli.add_argument('--json', required=True, type=Path)
    cli.add_argument('--samples', type=positive, default=3)
    cli.add_argument('--cpu', type=int, default=1)
    cli.add_argument('--workload', choices=NAMES, action='append', dest='workloads')
    args = cli.parse_args()
    os.sched_setaffinity(0, {args.cpu})
    measure(args.reference, args.previous, args.candidate, args.json, args.samples, args.workloads)
