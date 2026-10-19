"""Measure stage regressions against a pinned toolchain and the previous stage.

Run on an otherwise quiet Linux host with --cpu N. Exit 1 means a regression or
inconclusive comparison; --require-targets also requires the absolute budgets.
This is a local stage gate, not a timing assertion on shared CI workers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from tools.sloppy_core import benchmark_apps, benchmark_compile

ROOT = benchmark_compile.ROOT
REFERENCE = Path(__file__).with_name('performance_reference.json')


def tree_digest(root: Path) -> str:
    result = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file():
            result.update(path.relative_to(root).as_posix().encode() + b'\0')
            result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def toolchain_identity(binary: Path) -> dict:
    root = binary.parent.parent
    if (root / 'HOST_BUILD.json').is_file():
        host = json.loads((root / 'HOST_BUILD.json').read_text())
        manifest = host['source_build']
        expected_binary = host['compiler_sha256']
    else:
        manifest = json.loads((root / 'build.json').read_text())
        expected_binary = manifest['core_sha256']
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    if digest != expected_binary:
        raise ValueError(f'Compiler does not match its build manifest: {binary}')
    for directory in ('compiler', 'lib'):
        if not (root / directory).is_dir():
            raise ValueError(f'Missing toolchain {directory}: {root}')
        actual = {p.relative_to(root).as_posix() for p in (root / directory).rglob('*') if p.is_file()}
        expected = {p for p in manifest['sources_sha256'] if p.startswith(directory + '/')}
        if actual != expected:
            raise ValueError(f'Toolchain {directory} file set changed after its build: {root}')
        for name in actual:
            path = root / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sources_sha256'][name]:
                raise ValueError(f'Toolchain source changed after its build: {path}')
    return {'binary_sha256': digest, 'compiler_sources_sha256': tree_digest(root / 'compiler'),
            'library_sha256': tree_digest(root / 'lib')}


def compare_samples(before: list[float], after: list[float], limit: float = 1.02) -> dict:
    if len(before) != len(after) or len(before) < 7:
        raise ValueError('Need at least seven matched samples of each variant')
    if any(not math.isfinite(x) or x <= 0 for x in [*before, *after]):
        raise ValueError('Samples must be finite and positive')
    if not math.isfinite(limit) or limit < 1:
        raise ValueError('Regression limit must be finite and at least one')
    ratios = [b / a for a, b in zip(before, after, strict=True)]
    rng = random.Random(0)
    bootstrap = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(2000))
    low, high = bootstrap[50], bootstrap[1949]
    status = 'pass' if high <= limit else 'regression' if low > limit else 'inconclusive'
    return {'paired_median_ratio': statistics.median(ratios),
            'bootstrap_95_percent_interval': [low, high], 'limit': limit, 'status': status}


def assess(compilation: dict, runtime: dict, references: list[str], lines: int,
           limit: float = 1.02) -> dict:
    if not references or not compilation['workloads'] or not runtime['workloads'] or lines <= 0:
        raise ValueError('Both workload groups, reference labels and a source line count are required')
    comparisons = {}
    for name, workload in compilation['workloads'].items():
        for reference in references:
            comparisons[f'compile/{name}/{reference}'] = compare_samples(
                workload['cpu_seconds'][reference], workload['cpu_seconds']['candidate'], limit)
    for name, workload in runtime['workloads'].items():
        for mode in ('default', 'release'):
            proof = workload.get('unchanged_runtime_proof')
            if proof:
                for reference in references:
                    comparisons[f'runtime/{name}/{mode}/{reference}'] = {
                        **proof, 'status': 'pass', 'paired_median_ratio': None, 'limit': limit}
                continue
            candidate = [row['kernel_ns'] for row in workload['samples'][f'candidate-{mode}']]
            for reference in references:
                before = [row['kernel_ns'] for row in workload['samples'][f'{reference}-{mode}']]
                comparison = compare_samples(before, candidate, limit)
                hashes = workload.get('binary_sha256', {})
                if hashes.get(f'candidate-{mode}') and hashes.get(f'candidate-{mode}') == hashes.get(f'{reference}-{mode}'):
                    comparison['status'] = 'pass'
                    comparison['evidence'] = 'identical generated artifact; timing variation cannot be a code regression'
                else:
                    artifacts = workload.get('artifact_identity', {})
                    left = artifacts.get(f'{reference}-{mode}', {})
                    right = artifacts.get(f'candidate-{mode}', {})
                    if benchmark_apps.equivalent_artifact(left, right):
                        comparison['status'] = 'pass'
                        comparison['evidence'] = ('identical generated artifact except equal-width compiler bundle '
                                                  'paths; all code, layout and other data are byte-identical')
                comparisons[f'runtime/{name}/{mode}/{reference}'] = comparison
    throughput = lines / statistics.median(compilation['workloads']['throughput-default']['cpu_seconds']['candidate'])
    c_comparisons = {name: (None if workload.get('unchanged_runtime_proof') else
                           compare_samples([row['kernel_ns'] for row in workload['samples']['c']],
                                           [row['kernel_ns'] for row in workload['samples']['candidate-release']],
                                           limit=1.0))
                     for name, workload in runtime['workloads'].items()}
    c_ratios = {name: comparison['paired_median_ratio'] if comparison else None
                for name, comparison in c_comparisons.items()}
    runtime_targets_measured = all(ratio is not None for ratio in c_ratios.values())
    c_parity = runtime_targets_measured and all(ratio <= 1 for ratio in c_ratios.values())
    return {'comparisons': comparisons,
            'no_regression': all(row['status'] == 'pass' for row in comparisons.values()),
            'targets': {'fresh_default_root_lines_per_cpu_second': throughput,
                        'compile_goal_lines_per_second': 250000,
                        'release_kernel_ratios_to_c': c_ratios,
                        'release_kernel_comparisons_to_c': c_comparisons,
                        'all_runtime_targets_measured': runtime_targets_measured,
                        'at_or_faster_than_c_on_all_kernels': c_parity,
                        'met_on_these_workloads': throughput >= 250000 and c_parity},
            'limits': ['A 2% timing resolution is not a per-stage slowdown budget; compare both references.',
                       'Bootstrap intervals are approximate; inconclusive results require an isolated recheck.',
                       'Passing measured budgets does not establish language completeness or universal C parity.']}


def save_report(path: Path, report: dict) -> None:
    """Replace a checkpoint atomically; never leave a truncated JSON report."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix=path.name + '.',
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(report, indent=2) + '\n')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def measure(reference: Path, previous: Path, candidate: Path, samples: int,
            on_progress: Callable[[dict], None] | None = None,
            previous_report: Path | None = None) -> dict:
    # Keep the generic benchmark analysis importable on non-Linux test hosts.
    from tools.sloppy_core.benchmark_sloppy import generate_dewy

    if samples < 7:
        raise ValueError('The stage gate needs at least seven samples')
    pinned = json.loads(REFERENCE.read_text())
    identity = toolchain_identity(reference)
    for key in ('compiler_sources_sha256', 'library_sha256'):
        if identity[key] != pinned[key]:
            raise ValueError(f'Reference {key} does not match the pinned stage; do not ratchet the baseline')
    compilers = {'reference': reference, 'candidate': candidate}
    identities = {'reference': identity, 'candidate': toolchain_identity(candidate)}
    prior_identity = toolchain_identity(previous)
    if prior_identity != identity:
        compilers['previous'] = previous
        identities['previous'] = prior_identity
    references = [label for label in compilers if label != 'candidate']
    report = {'reference_stage': pinned, 'toolchains': identities, 'status': 'incomplete'}
    certificate = None
    if previous_report is not None:
        from tools.sloppy_core.runtime_certificate import RuntimeCertificate

        certificate = RuntimeCertificate(previous_report, identities)
        report['accepted_previous_report_sha256'] = certificate.report_sha256

    def checkpoint(section: str, result: dict) -> None:
        # Only called between completed workloads, outside every timed region.
        # No assessment is published until all measurements and identities pass.
        report[section] = result
        if on_progress is not None:
            on_progress(report)

    report['cpu_model'] = next((line.split(':', 1)[1].strip() for line in
                              Path('/proc/cpuinfo').read_text().splitlines()
                              if line.startswith('model name')), '')
    if on_progress is not None:
        on_progress(report)
    scratch = ROOT / '__dewycache__/task-tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    saved_workloads = benchmark_compile.WORKLOADS.copy()
    try:
        with tempfile.TemporaryDirectory(prefix='stage-performance-', dir=scratch) as directory:
            source = Path(directory) / 'large.dewy'
            source.write_text(generate_dewy(2000))
            benchmark_compile.WORKLOADS.update({
                'throughput-default': ('build', str(source)),
                'throughput-release': ('build', str(source), '--release'),
                'compiler-reference': ('build', str(reference.parent.parent / 'compiler/main.jo')),
            })
            checked_outputs = {}

            def validate(name: str, label: str, binary: Path) -> bool:
                # Games need a window; the throughput workload is headless and
                # invokes all 2,000 generated functions. Validate outside timing.
                if not name.startswith('throughput-'):
                    return False
                ran = subprocess.run([binary], capture_output=True, text=True,
                                     timeout=30, check=True)
                value = float(ran.stdout.strip())
                if not math.isclose(value, 102380577.8970889, rel_tol=1e-12):
                    raise ValueError(f'{name}/{label}: wrong generated-program result: {value}')
                checked_outputs[f'{name}/{label}'] = value
                return True

            report['compilation'] = benchmark_compile.measure(compilers, [
                'throughput-default', 'throughput-release', 'tour-default',
                'netpong-default', 'dunes-default', 'compiler-reference'], samples, 1, validate,
                on_progress=lambda result: checkpoint('compilation', result))
            report['compilation']['validated_outputs'] = checked_outputs
            report['runtime'] = benchmark_apps.measure(compilers, list(benchmark_apps.COUNTS),
                                                       samples, 'cc', clock='thread-cpu', mode='both',
                                                       reuse_identical_artifacts=True,
                                                       on_progress=lambda result: checkpoint('runtime', result),
                                                       unchanged_proof=certificate.prove if certificate else None)
            lines = len(source.read_text().splitlines())
    finally:
        benchmark_compile.WORKLOADS.clear()
        benchmark_compile.WORKLOADS.update(saved_workloads)
    # A stage cannot pass using a toolchain that changed during measurement.
    for label, binary in compilers.items():
        if toolchain_identity(binary) != identities[label]:
            raise ValueError(f'Toolchain changed during the gate: {label}')
    report['assessment'] = assess(report['compilation'], report['runtime'], references, lines)
    report['status'] = 'complete'
    return report


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--reference', type=Path, required=True)
    cli.add_argument('--previous', type=Path, required=True)
    cli.add_argument('--candidate', type=Path, required=True)
    cli.add_argument('--samples', type=int, default=9)
    cli.add_argument('--cpu', type=int, required=True)
    cli.add_argument('--require-targets', action='store_true')
    cli.add_argument('--previous-report', type=Path,
                     help='Accepted previous stage: prove unchanged runtime artifacts instead of retiming them')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    os.sched_setaffinity(0, {args.cpu})
    report = measure(args.reference.resolve(strict=True), args.previous.resolve(strict=True),
                     args.candidate.resolve(strict=True), args.samples,
                     on_progress=lambda partial: save_report(args.output, partial),
                     previous_report=None if args.require_targets else args.previous_report)
    save_report(args.output, report)
    assessment = report['assessment']
    for name, result in assessment['comparisons'].items():
        ratio = result['paired_median_ratio']
        detail = result['evidence'] if ratio is None else f'paired CPU ratio {ratio:.4f}'
        print(f'{name}: {result["status"]}, {detail}')
    print(json.dumps(assessment['targets'], indent=2))
    return int(not assessment['no_regression'] or
               (args.require_targets and not assessment['targets']['met_on_these_workloads']))


if __name__ == '__main__':
    raise SystemExit(main())
